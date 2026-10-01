"""Claude Code CLI-backed provider using a Claude Pro/Max subscription OAuth token.

Mirrors ``CodexCLIProvider``: Mira's prompts and tool schemas go in, the same JSON
strings come out. Model execution happens through ``claude -p`` authenticated by
``CLAUDE_CODE_OAUTH_TOKEN`` (from ``claude setup-token``) instead of an API key.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import tempfile

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from mira.exceptions import LLMError
from mira.llm.codex_cli import _SAFE_ENV_KEYS, CodexCLIProvider

logger = logging.getLogger(__name__)

TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"


class ClaudeCLIProvider(CodexCLIProvider):
    """LLM provider that shells out to Anthropic's Claude Code CLI in print mode.

    Reuses the Codex provider's prompt building, JSON extraction, process cleanup,
    and single-shot review behaviour; only the subprocess invocation differs.
    """

    def _claude_env(self, runtime_home: str) -> dict[str, str]:
        """Minimal child env: safe keys plus the OAuth token, nothing else.

        Deliberately drops ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL so the CLI can't
        silently switch to metered API billing or a different endpoint.
        """
        token = os.environ.get(TOKEN_ENV)
        if not token:
            raise LLMError("claude_token_missing", env=TOKEN_ENV)
        env = {key: value for key, value in os.environ.items() if key in _SAFE_ENV_KEYS}
        env.update(
            {
                "HOME": runtime_home,
                "USERPROFILE": runtime_home,
                TOKEN_ENV: token,
                "DISABLE_AUTOUPDATER": "1",
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            }
        )
        return env

    def _claude_command(self) -> list[str]:
        claude_command = self.config.claude_command or "claude"
        if any(char in claude_command for char in (" ", "\t", "\n", ";", "|", "&")):
            raise ValueError(
                f"Invalid claude_command: {claude_command!r}. "
                "Set it to a single executable path/name without arguments."
            )
        cmd = [
            claude_command,
            "-p",
            "--output-format",
            "json",
            "--tools",
            "",
            "--strict-mcp-config",
            "--no-session-persistence",
            "--disable-slash-commands",
        ]
        if self.config.model not in {"", "default", "claude-default"}:
            cmd.extend(["--model", self.config.model])
        return cmd

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(LLMError),
        reraise=True,
    )
    async def _run_codex(self, prompt: str) -> str:
        with tempfile.TemporaryDirectory(prefix="mira-claude-") as runtime_home:
            cmd = self._claude_command()
            logger.debug("Running Claude CLI provider: %s", shlex.join(cmd))
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=self._claude_env(runtime_home),
                    cwd=runtime_home,
                    start_new_session=os.name == "posix",
                )
            except FileNotFoundError as exc:
                raise LLMError(
                    "claude_command_not_found", command=self.config.claude_command
                ) from exc

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(prompt.encode("utf-8")),
                    timeout=self.config.claude_timeout_seconds,
                )
            except TimeoutError as exc:
                await self._terminate_process_tree(proc)
                raise LLMError(
                    "claude_timeout", seconds=self.config.claude_timeout_seconds
                ) from exc
            except BaseException:
                await self._terminate_process_tree(proc)
                raise

            stdout_text = stdout.decode("utf-8", errors="replace").strip()
            try:
                payload = json.loads(stdout_text)
            except json.JSONDecodeError:
                payload = None
            if proc.returncode != 0 or not isinstance(payload, dict) or payload.get("is_error"):
                detail = (
                    (payload if isinstance(payload, dict) else {}).get("result")
                    or stderr.decode("utf-8", errors="replace")
                    or stdout_text
                )
                raise LLMError(
                    "claude_exit_failed",
                    exit_code=proc.returncode,
                    detail=str(detail).strip()[-2000:],
                )
            return str(payload.get("result") or "").strip()

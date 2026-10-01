from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from mira.config import LLMConfig
from mira.dashboard.model_catalog import active_backend, build_options
from mira.exceptions import LLMError
from mira.llm import create_llm
from mira.llm.claude_cli import ClaudeCLIProvider


def _spawn(monkeypatch, stdout: bytes, returncode: int = 0) -> AsyncMock:
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate.return_value = (stdout, b"")
    spawn = AsyncMock(return_value=proc)
    monkeypatch.setattr("asyncio.create_subprocess_exec", spawn)
    return spawn


class TestClaudeCLIProvider:
    def test_factory_selects_claude_cli_provider(self):
        assert isinstance(create_llm(LLMConfig(provider="claude-cli")), ClaudeCLIProvider)

    def test_command_disables_tools_and_passes_model(self):
        provider = ClaudeCLIProvider(
            LLMConfig(provider="claude-cli", model="sonnet", claude_command="/usr/bin/claude")
        )
        assert provider._claude_command() == [
            "/usr/bin/claude",
            "-p",
            "--output-format",
            "json",
            "--tools",
            "",
            "--strict-mcp-config",
            "--no-session-persistence",
            "--disable-slash-commands",
            "--model",
            "sonnet",
        ]

    def test_command_omits_model_for_claude_default(self):
        cmd = ClaudeCLIProvider(
            LLMConfig(provider="claude-cli", model="claude-default")
        )._claude_command()
        assert "--model" not in cmd

    def test_command_rejects_arguments(self):
        provider = ClaudeCLIProvider(LLMConfig(provider="claude-cli", claude_command="claude -x"))
        with pytest.raises(ValueError, match="Invalid claude_command"):
            provider._claude_command()

    def test_env_passes_only_token_and_safe_keys(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat01-x")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "metered")
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://evil.example")
        monkeypatch.setenv("GITHUB_TOKEN", "do-not-inherit")
        env = ClaudeCLIProvider(LLMConfig(provider="claude-cli"))._claude_env(str(tmp_path))
        assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-oat01-x"
        assert env["HOME"] == str(tmp_path)
        for leaked in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "GITHUB_TOKEN"):
            assert leaked not in env

    def test_env_requires_token(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        with pytest.raises(LLMError, match="CLAUDE_CODE_OAUTH_TOKEN"):
            ClaudeCLIProvider(LLMConfig(provider="claude-cli"))._claude_env(str(tmp_path))

    @pytest.mark.asyncio
    async def test_review_returns_tool_arguments_from_result(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "t")
        body = {"type": "result", "is_error": False, "result": '{"comments": [], "summary": "ok"}'}
        spawn = _spawn(monkeypatch, json.dumps(body).encode())
        provider = ClaudeCLIProvider(LLMConfig(provider="claude-cli"))

        result = await provider.review([{"role": "user", "content": "review"}])

        assert json.loads(result) == {"comments": [], "summary": "ok"}
        assert spawn.await_args.kwargs["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "t"

    @pytest.mark.asyncio
    async def test_error_result_raises(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "t")
        body = {"type": "result", "is_error": True, "result": "Invalid API key"}
        _spawn(monkeypatch, json.dumps(body).encode(), returncode=1)
        provider = ClaudeCLIProvider(LLMConfig(provider="claude-cli"))

        with pytest.raises(LLMError, match="Invalid API key"):
            await provider._run_codex("x")

    def test_dashboard_offers_only_claude_models(self):
        backend = active_backend(LLMConfig(provider="claude-cli"))
        assert backend == "claude-cli"
        values = {m["value"] for m in build_options(backend, None, "review")}
        assert values == {"claude-default", "sonnet", "opus", "haiku"}
        assert "sonnet" not in {m["value"] for m in build_options("openrouter", None, "review")}

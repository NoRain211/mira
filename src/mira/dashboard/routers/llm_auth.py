"""Dashboard routes for choosing the model provider and signing in to subscriptions.

ChatGPT: runs `codex login --device-auth` and surfaces its link + one-time code.
Claude: stores the token printed by `claude setup-token`.
"""

from __future__ import annotations

import asyncio
import os
import re

from fastapi import HTTPException, Request
from pydantic import BaseModel

from mira.dashboard import api as _api
from mira.dashboard.api import _require_admin, logger, router
from mira.llm import subscription_auth

PROVIDERS = {"openai", "codex-cli", "claude-cli"}
# Models applied when switching provider; "" = inherit from mira.yaml.
_PROVIDER_MODELS = {
    "openai": {"indexing_model": "", "review_model": "", "security_model": ""},
    "codex-cli": {
        "indexing_model": "codex-default",
        "review_model": "codex-default",
        "security_model": "codex-default",
    },
    "claude-cli": {"indexing_model": "haiku", "review_model": "sonnet", "security_model": "sonnet"},
}
_ALIASES = {
    "codex": "codex-cli",
    "codex_cli": "codex-cli",
    "claude_cli": "claude-cli",
    "claude-code": "claude-cli",
}
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_URL = re.compile(r"https://\S+")
_CODE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4,6}\b")

# ponytail: one in-process device login at a time; fine for a single dashboard replica.
_codex_login: dict = {"proc": None, "url": None, "code": None, "error": None}


class ProviderUpdate(BaseModel):
    provider: str


class ClaudeToken(BaseModel):
    token: str


@router.get("/api/settings/llm-provider")
def get_llm_provider(request: Request) -> dict:
    _require_admin(request)
    from mira.config import load_config

    provider = load_config().llm.provider
    proc = _codex_login["proc"]
    pending = proc is not None and proc.returncode is None
    return {
        "provider": _ALIASES.get(provider, provider),
        "codex": {
            "connected": subscription_auth.codex_connected(),
            "pending": {"url": _codex_login["url"], "code": _codex_login["code"]}
            if pending
            else None,
            "error": _codex_login["error"],
        },
        "claude": {
            "connected": bool(
                subscription_auth.read_claude_token() or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
            ),
        },
    }


@router.put("/api/settings/llm-provider")
def set_llm_provider(body: ProviderUpdate, request: Request) -> dict:
    _require_admin(request)
    if body.provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"provider must be one of {sorted(PROVIDERS)}")
    _api._app_db.set_setting("llm_provider", body.provider)
    for key, value in _PROVIDER_MODELS[body.provider].items():
        _api._app_db.set_setting(key, value)
    return {"ok": True}


async def _wait_codex_login(proc: asyncio.subprocess.Process, lines: list[str]) -> None:
    assert proc.stdout is not None
    async for raw in proc.stdout:
        lines.append(_ANSI.sub("", raw.decode("utf-8", errors="replace")).rstrip())
    await proc.wait()
    if proc.returncode != 0 and not subscription_auth.codex_connected():
        _codex_login["error"] = "\n".join(lines[-5:]) or f"codex login exited {proc.returncode}"
        logger.warning("ChatGPT device login failed: %s", _codex_login["error"])


@router.post("/api/settings/codex-login")
async def start_codex_login(request: Request) -> dict:
    """Start ChatGPT device-code sign-in; returns the link and one-time code."""
    _require_admin(request)
    old = _codex_login["proc"]
    if old is not None and old.returncode is None:
        old.kill()
    home = subscription_auth.codex_home()
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    env = {k: v for k, v in os.environ.items() if k in {"PATH", "LANG", "SSL_CERT_FILE"}}
    env.update({"CODEX_HOME": str(home), "HOME": str(home), "NO_COLOR": "1"})
    try:
        proc = await asyncio.create_subprocess_exec(
            "codex",
            "login",
            "--device-auth",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.DEVNULL,
            env=env,
            cwd=str(home),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="codex CLI is not installed") from exc
    _codex_login.update(proc=proc, url=None, code=None, error=None)

    assert proc.stdout is not None
    lines: list[str] = []
    try:
        async with asyncio.timeout(30):
            while not (_codex_login["url"] and _codex_login["code"]):
                raw = await proc.stdout.readline()
                if not raw:
                    break
                line = _ANSI.sub("", raw.decode("utf-8", errors="replace")).rstrip()
                lines.append(line)
                if (m := _URL.search(line)) and not _codex_login["url"]:
                    _codex_login["url"] = m.group(0)
                elif (m := _CODE.search(line)) and _codex_login["url"]:
                    _codex_login["code"] = m.group(0)
    except TimeoutError:
        pass
    if not (_codex_login["url"] and _codex_login["code"]):
        proc.kill()
        raise HTTPException(
            status_code=502, detail="Could not start ChatGPT sign-in: " + " ".join(lines[-3:])
        )
    asyncio.create_task(_wait_codex_login(proc, lines))
    return {"url": _codex_login["url"], "code": _codex_login["code"]}


@router.delete("/api/settings/codex-login")
def codex_logout(request: Request) -> dict:
    _require_admin(request)
    (subscription_auth.codex_home() / "auth.json").unlink(missing_ok=True)
    return {"ok": True}


@router.put("/api/settings/claude-token")
def save_claude_token(body: ClaudeToken, request: Request) -> dict:
    _require_admin(request)
    token = body.token.strip()
    if not token.startswith("sk-ant-"):
        raise HTTPException(
            status_code=400, detail="Paste the sk-ant-… token from claude setup-token"
        )
    subscription_auth.write_claude_token(token)
    return {"ok": True}


@router.delete("/api/settings/claude-token")
def clear_claude_token(request: Request) -> dict:
    _require_admin(request)
    subscription_auth.clear_claude_token()
    return {"ok": True}

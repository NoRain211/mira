"""Dashboard-managed subscription credentials for the codex-cli / claude-cli providers.

Stored as owner-only files next to the app database (MIRA_INDEX_DIR), never in the DB
or API responses. When present they take precedence over CODEX_HOME /
CLAUDE_CODE_OAUTH_TOKEN, because they come from an explicit dashboard sign-in.
"""

from __future__ import annotations

import os
from pathlib import Path


def auth_dir() -> Path:
    return Path(os.environ.get("MIRA_INDEX_DIR", "./data/indexes")) / "_llm_auth"


def codex_home() -> Path:
    """CODEX_HOME that `codex login` writes to from the dashboard."""
    return auth_dir() / "codex"


def codex_connected() -> bool:
    return (codex_home() / "auth.json").is_file()


def _claude_token_file() -> Path:
    return auth_dir() / "claude_oauth_token"


def read_claude_token() -> str | None:
    try:
        return _claude_token_file().read_text(encoding="utf-8").strip() or None
    except FileNotFoundError:
        return None


def write_claude_token(token: str) -> None:
    path = _claude_token_file()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token)


def clear_claude_token() -> None:
    _claude_token_file().unlink(missing_ok=True)

"""Dashboard model-provider selection and subscription sign-in storage."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import mira.config as mira_config
from mira.config import LLMConfig, load_config
from mira.dashboard.db import AppDatabase
from mira.dashboard.routers.llm_auth import (
    ClaudeToken,
    ProviderUpdate,
    get_llm_provider,
    save_claude_token,
    set_llm_provider,
)
from mira.llm import subscription_auth
from mira.llm.claude_cli import ClaudeCLIProvider
from mira.llm.codex_cli import CodexCLIProvider

ADMIN = SimpleNamespace(state=SimpleNamespace(user=SimpleNamespace(is_admin=True)))


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppDatabase:
    monkeypatch.setenv("MIRA_INDEX_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)  # no stray .mira.yaml
    monkeypatch.setattr(mira_config, "_global_defaults", {})
    app_db = AppDatabase(url="", admin_password="admin")
    monkeypatch.setattr("mira.dashboard.api._app_db", app_db)
    return app_db


def test_switching_provider_applies_to_config_and_models(db: AppDatabase):
    set_llm_provider(ProviderUpdate(provider="claude-cli"), ADMIN)

    assert load_config().llm.provider == "claude-cli"
    assert db.get_setting("review_model") == "sonnet"
    assert db.get_setting("indexing_model") == "haiku"
    assert get_llm_provider(ADMIN)["provider"] == "claude-cli"


def test_unknown_provider_rejected(db: AppDatabase):
    with pytest.raises(HTTPException):
        set_llm_provider(ProviderUpdate(provider="bedrock"), ADMIN)


def test_claude_token_saved_to_file_and_preferred_over_env(
    db: AppDatabase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-from-env")
    with pytest.raises(HTTPException):
        save_claude_token(ClaudeToken(token="not-a-token"), ADMIN)

    save_claude_token(ClaudeToken(token=" sk-ant-oat01-dash \n"), ADMIN)

    env = ClaudeCLIProvider(LLMConfig(provider="claude-cli"))._claude_env(str(tmp_path))
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-oat01-dash"
    assert "sk-ant-oat01-dash" not in str(get_llm_provider(ADMIN))


def test_dashboard_codex_login_preferred_over_mounted_home(db: AppDatabase, tmp_path: Path):
    mounted = tmp_path / "mounted"
    mounted.mkdir()
    (mounted / "auth.json").write_text('{"from": "mount"}')
    managed = subscription_auth.codex_home()
    managed.mkdir(parents=True)
    (managed / "auth.json").write_text('{"from": "dashboard"}')

    provider = CodexCLIProvider(LLMConfig(provider="codex-cli", codex_home=str(mounted)))
    runtime = Path(provider._prepare_codex_home(str(tmp_path / "run")))

    assert (runtime / "auth.json").read_text() == '{"from": "dashboard"}'

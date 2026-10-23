"""repository.renamed moves a repo's registry row, history, and index to the new name."""

from __future__ import annotations

from pathlib import Path

import pytest

from mira.dashboard.db import AppDatabase
from mira.index.store import IndexStore
from mira.platforms.github import webhook


async def test_repo_renamed_moves_all_repo_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MIRA_INDEX_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db = AppDatabase(url=str(tmp_path / "app.db"), admin_password="admin")
    monkeypatch.setattr(webhook, "_get_app_db", lambda: db)

    db.register_repo("o", "old")
    db.upsert_pull_request("o", "old", 1, author="alice")
    store = IndexStore.open("o", "old")
    rule_id = store.create_learned_rule("rule", "bug", status="pending").id
    store.close()

    payload = {
        "action": "renamed",
        "repository": {"name": "new", "owner": {"login": "o"}},
        "changes": {"repository": {"name": {"from": "old"}}},
    }
    await webhook.handle_repo_renamed(payload, None, "mira")  # type: ignore[arg-type]

    assert db.get_repo("o", "new") is not None
    assert db.get_repo("o", "old") is None
    assert db._sqlite_conn.execute("SELECT repo FROM pull_requests").fetchall() == [("new",)]
    assert not (tmp_path / "o" / "old.db").exists()
    store = IndexStore.open("o", "new")
    rule = store.get_learned_rule(rule_id)
    store.close()
    assert rule is not None and rule.status == "pending"


async def test_repo_renamed_after_sync_drops_stale_registry_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MIRA_INDEX_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db = AppDatabase(url=str(tmp_path / "app.db"), admin_password="admin")
    db.register_repo("o", "old")
    db.register_repo("o", "new")  # a repo sync already picked up the new name

    db.rename_repo("o", "old", "new")

    assert [r.repo for r in db.get_repo_any_platform("o", "new")] == ["new"]
    assert db.get_repo("o", "old") is None

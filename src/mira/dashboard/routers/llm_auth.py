"""Dashboard routes for subscription accounts (ChatGPT / Claude OAuth)."""

from __future__ import annotations

from fastapi import HTTPException, Request
from pydantic import BaseModel

from mira.dashboard.api import _require_admin, router
from mira.exceptions import LLMError
from mira.llm import oauth_accounts


class AnthropicCode(BaseModel):
    login_id: str
    code: str


def _account_key(provider: str) -> str:
    if provider not in oauth_accounts.PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider")
    return provider


def _forget_catalog() -> None:
    from mira.dashboard import model_catalog

    for account in oauth_accounts.PROVIDERS:
        model_catalog._cache.pop(account, None)


@router.get("/api/llm-accounts")
def get_accounts(request: Request) -> dict:
    _require_admin(request)
    return {"accounts": oauth_accounts.public_accounts()}


@router.post("/api/llm-accounts/{provider}/login")
async def start_login(provider: str, request: Request) -> dict:
    _require_admin(request)
    try:
        if _account_key(provider) == "chatgpt":
            return await oauth_accounts.start_chatgpt_login()
        return await oauth_accounts.start_anthropic_login()
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/api/llm-accounts/logins/{login_id}")
def login_status(login_id: str, request: Request) -> dict:
    _require_admin(request)
    status = oauth_accounts.login_status(login_id)
    if status["status"] == "done":
        _forget_catalog()
    return status


@router.post("/api/llm-accounts/anthropic/complete")
async def complete_anthropic(body: AnthropicCode, request: Request) -> dict:
    """Finish Claude sign-in with a pasted redirect URL or code (when the callback can't reach Mira)."""
    _require_admin(request)
    try:
        await oauth_accounts.complete_anthropic_login(body.login_id, body.code)
    except LLMError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _forget_catalog()
    return {"ok": True}


@router.post("/api/llm-accounts/{provider}/{account_id}/activate")
async def activate_account(provider: str, account_id: str, request: Request) -> dict:
    _require_admin(request)
    try:
        await oauth_accounts.activate(_account_key(provider), account_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown account") from exc
    _forget_catalog()
    return {"ok": True}


@router.delete("/api/llm-accounts/{provider}/{account_id}")
async def remove_account(provider: str, account_id: str, request: Request) -> dict:
    _require_admin(request)
    await oauth_accounts.remove(_account_key(provider), account_id)
    _forget_catalog()
    return {"ok": True}


@router.delete("/api/llm-accounts/{provider}")
async def log_out(provider: str, request: Request) -> dict:
    _require_admin(request)
    await oauth_accounts.remove(_account_key(provider))
    _forget_catalog()
    return {"ok": True}

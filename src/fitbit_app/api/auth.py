"""Google account connection: /api/auth/login, /callback, /status, /logout."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import secrets
import time
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from fitbit_app.api.deps import get_settings_dep, get_sync_service
from fitbit_app.config import Settings
from fitbit_app.errors import ConfigError, GoogleApiError, OAuthError, ReauthRequiredError
from fitbit_app.ingest.client import GoogleHealthClient, StaticToken
from fitbit_app.ingest.endpoints import API_BASE_URL
from fitbit_app.ingest.oauth import (
    build_authorization_url,
    exchange_code,
    new_pkce_pair,
    revoke_token,
)
from fitbit_app.ingest.scopes import missing_scopes
from fitbit_app.ingest.service import SyncService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

PENDING_TTL_S = 600
SETTINGS_PAGE = "/settings"

SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SyncDep = Annotated[SyncService, Depends(get_sync_service)]


class AuthStatus(BaseModel):
    configured: bool
    secret_key_configured: bool
    connected: bool
    needs_reauth: bool
    health_user_id: str | None = None
    missing_scopes: list[str] = Field(default_factory=list)
    expires_at: dt.datetime | None = None


def _pending(request: Request) -> dict[str, tuple[str, float]]:
    """state -> (PKCE verifier, created). In memory: a restart just means "connect again"."""
    pending: dict[str, tuple[str, float]] = request.app.state.oauth_pending
    cutoff = time.monotonic() - PENDING_TTL_S
    for state in [s for s, (_, created) in pending.items() if created < cutoff]:
        del pending[state]
    return pending


def _back_to_settings(**params: str) -> RedirectResponse:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"{SETTINGS_PAGE}?{query}", status_code=303)


@router.get("/login")
async def login(request: Request, settings: SettingsDep) -> RedirectResponse:
    if not settings.google_configured:
        raise HTTPException(400, "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env")
    if not settings.secret_key_configured:
        raise HTTPException(400, "Set FITBIT_SECRET_KEY in .env")
    state = secrets.token_urlsafe(32)
    verifier, challenge = new_pkce_pair()
    _pending(request)[state] = (verifier, time.monotonic())
    return RedirectResponse(build_authorization_url(settings, state, challenge), status_code=302)


@router.get("/callback")
async def callback(
    request: Request,
    settings: SettingsDep,
    sync_service: SyncDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error:
        # e.g. access_denied when the user cancels the consent screen.
        return _back_to_settings(auth_error=error)
    entry = _pending(request).pop(state or "", None)
    if entry is None or not code:
        return _back_to_settings(auth_error="invalid_state")
    verifier, _ = entry

    try:
        async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as http:
            tokens = await exchange_code(http, settings, code, verifier)
            # Confirms the Google Health profile exists (else 400 ACCOUNT_NOT_LINKED).
            client = GoogleHealthClient(http, StaticToken(tokens.access_token))
            identity = await client.get_identity()
    except GoogleApiError as exc:
        logger.warning("Identity check failed: %s", exc.reason)
        reason = "account_not_linked" if exc.reason == "ACCOUNT_NOT_LINKED" else "api_error"
        return _back_to_settings(auth_error=reason)
    except (OAuthError, ReauthRequiredError, httpx.HTTPError) as exc:
        logger.warning("OAuth callback failed: %s", type(exc).__name__)
        return _back_to_settings(auth_error="exchange_failed")

    try:
        await asyncio.to_thread(sync_service.token_store.save, tokens, identity.get("healthUserId"))
    except ConfigError as exc:
        logger.error("Cannot store tokens: %s", exc)
        return _back_to_settings(auth_error="secret_key")

    logger.info("Google account connected; starting initial sync")
    sync_service.start_background()
    return _back_to_settings(connected="1")


@router.get("/status", response_model=AuthStatus)
def status(settings: SettingsDep, sync_service: SyncDep) -> AuthStatus:
    stored = sync_service.token_store.load()
    return AuthStatus(
        configured=settings.google_configured,
        secret_key_configured=settings.secret_key_configured,
        connected=stored is not None,
        needs_reauth=bool(stored and stored.needs_reauth),
        health_user_id=stored.health_user_id if stored else None,
        missing_scopes=missing_scopes(stored.scope) if stored else [],
        expires_at=stored.expires_at if stored else None,
    )


@router.post("/logout", status_code=204)
async def logout(sync_service: SyncDep) -> None:
    store = sync_service.token_store
    stored = await asyncio.to_thread(store.load)
    if stored is not None:
        async with httpx.AsyncClient(timeout=10.0) as http:
            await revoke_token(http, stored.access_token)
    await asyncio.to_thread(store.clear)

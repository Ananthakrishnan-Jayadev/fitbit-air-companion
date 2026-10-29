"""Google OAuth 2.0 (authorization code + PKCE, offline access) and token persistence.

Flow per https://developers.google.com/health/setup: auth endpoint with
access_type=offline, then token exchange; refresh on demand when close to expiry.
"""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import hashlib
import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.config import Settings
from fitbit_app.errors import ConfigError, NotConnectedError, OAuthError, ReauthRequiredError
from fitbit_app.ingest.endpoints import AUTH_URL, REVOKE_URL, TOKEN_URL
from fitbit_app.ingest.scopes import READ_SCOPES
from fitbit_app.storage.models import OAuthToken
from fitbit_app.storage.types import utcnow

logger = logging.getLogger(__name__)

TOKEN_ROW_ID = 1
# Refresh this long before expiry so a request never starts with a dying token.
REFRESH_MARGIN = dt.timedelta(minutes=2)


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: dt.datetime
    scope: str
    token_type: str


@dataclass(frozen=True)
class StoredToken:
    access_token: str
    expires_at: dt.datetime
    scope: str
    health_user_id: str | None
    needs_reauth: bool
    has_refresh_token: bool


# --- Authorization request ---------------------------------------------------------------


def new_pkce_pair() -> tuple[str, str]:
    """(code_verifier, S256 code_challenge)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_authorization_url(settings: Settings, state: str, code_challenge: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(READ_SCOPES),
        "access_type": "offline",
        # Always show consent so Google returns a refresh token on every connect.
        "prompt": "consent",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


# --- Token endpoint ----------------------------------------------------------------------


async def exchange_code(
    http: httpx.AsyncClient, settings: Settings, code: str, code_verifier: str
) -> TokenSet:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": settings.google_redirect_uri,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret.get_secret_value(),
    }
    response = await http.post(TOKEN_URL, data=data)
    if response.status_code != 200:
        raise OAuthError(f"Code exchange failed: {_oauth_error(response)}")
    return _token_set(response.json())


async def refresh_access_token(
    http: httpx.AsyncClient, settings: Settings, refresh_token: str
) -> TokenSet:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret.get_secret_value(),
    }
    response = await http.post(TOKEN_URL, data=data)
    if response.status_code in (400, 401):
        # invalid_grant: revoked, or expired (Testing-mode refresh tokens last 7 days).
        raise ReauthRequiredError(f"Token refresh rejected: {_oauth_error(response)}")
    if response.status_code != 200:
        raise OAuthError(f"Token refresh failed: HTTP {response.status_code}")
    return _token_set(response.json())


async def revoke_token(http: httpx.AsyncClient, token: str) -> None:
    """Best effort; the local copy is deleted regardless."""
    try:
        response = await http.post(REVOKE_URL, data={"token": token})
        if response.status_code != 200:
            logger.warning("Token revoke returned HTTP %s", response.status_code)
    except httpx.HTTPError as exc:
        logger.warning("Token revoke failed: %s", type(exc).__name__)


def _token_set(body: dict[str, object]) -> TokenSet:
    expires_in = int(str(body.get("expires_in", 3600)))
    refresh = body.get("refresh_token")
    return TokenSet(
        access_token=str(body["access_token"]),
        refresh_token=str(refresh) if refresh else None,
        expires_at=utcnow() + dt.timedelta(seconds=expires_in),
        scope=str(body.get("scope", "")),
        token_type=str(body.get("token_type", "Bearer")),
    )


def _oauth_error(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    return f"HTTP {response.status_code} {body.get('error', '')}".strip()


# --- Persistence -------------------------------------------------------------------------


class TokenStore:
    """Single-row token storage. The refresh token is Fernet-encrypted at rest."""

    def __init__(self, session_factory: sessionmaker[Session], secret_key: SecretStr) -> None:
        self._session_factory = session_factory
        self._secret_key = secret_key

    def _fernet(self) -> Fernet:
        key = self._secret_key.get_secret_value()
        if not key:
            raise ConfigError("FITBIT_SECRET_KEY is not set; see .env.example")
        try:
            return Fernet(key.encode())
        except ValueError as exc:
            raise ConfigError("FITBIT_SECRET_KEY is not a valid Fernet key") from exc

    def load(self) -> StoredToken | None:
        with self._session_factory() as session:
            row = session.get(OAuthToken, TOKEN_ROW_ID)
            if row is None:
                return None
            return StoredToken(
                access_token=row.access_token,
                expires_at=row.expires_at,
                scope=row.scope,
                health_user_id=row.health_user_id,
                needs_reauth=row.needs_reauth,
                has_refresh_token=row.refresh_token_encrypted is not None,
            )

    def refresh_token(self) -> str:
        with self._session_factory() as session:
            row = session.get(OAuthToken, TOKEN_ROW_ID)
            if row is None:
                raise NotConnectedError("No Google account connected")
            if row.refresh_token_encrypted is None:
                raise ReauthRequiredError("No refresh token stored")
            encrypted = row.refresh_token_encrypted
        try:
            return self._fernet().decrypt(encrypted.encode()).decode()
        except InvalidToken as exc:
            raise ReauthRequiredError("Stored refresh token cannot be decrypted") from exc

    def save(self, tokens: TokenSet, health_user_id: str | None = None) -> None:
        encrypted = (
            self._fernet().encrypt(tokens.refresh_token.encode()).decode()
            if tokens.refresh_token
            else None
        )
        with self._session_factory() as session:
            row = session.get(OAuthToken, TOKEN_ROW_ID)
            if row is None:
                row = OAuthToken(id=TOKEN_ROW_ID)
                session.add(row)
            row.access_token = tokens.access_token
            row.expires_at = tokens.expires_at
            row.scope = tokens.scope
            row.token_type = tokens.token_type
            row.needs_reauth = False
            # Refresh responses usually omit the refresh token: keep the stored one.
            if encrypted is not None:
                row.refresh_token_encrypted = encrypted
            if health_user_id is not None:
                row.health_user_id = health_user_id
            session.commit()

    def mark_needs_reauth(self) -> None:
        with self._session_factory() as session:
            row = session.get(OAuthToken, TOKEN_ROW_ID)
            if row is not None:
                row.needs_reauth = True
                session.commit()

    def clear(self) -> None:
        with self._session_factory() as session:
            row = session.get(OAuthToken, TOKEN_ROW_ID)
            if row is not None:
                session.delete(row)
                session.commit()


class TokenManager:
    """Hands out a valid access token, refreshing (and persisting) when needed."""

    def __init__(
        self,
        store: TokenStore,
        http: httpx.AsyncClient,
        settings: Settings,
        clock: Callable[[], dt.datetime] = utcnow,
    ) -> None:
        self._store = store
        self._http = http
        self._settings = settings
        self._clock = clock
        self._lock = asyncio.Lock()

    async def access_token(self, *, force_refresh: bool = False) -> str:
        async with self._lock:
            stored = await asyncio.to_thread(self._store.load)
            if stored is None:
                raise NotConnectedError("No Google account connected")
            if stored.needs_reauth:
                raise ReauthRequiredError("Google connection needs to be renewed")
            if not force_refresh and stored.expires_at - REFRESH_MARGIN > self._clock():
                return stored.access_token

            refresh = await asyncio.to_thread(self._store.refresh_token)
            try:
                tokens = await refresh_access_token(self._http, self._settings, refresh)
            except ReauthRequiredError:
                await asyncio.to_thread(self._store.mark_needs_reauth)
                raise
            await asyncio.to_thread(self._store.save, tokens)
            logger.info("Refreshed Google access token")
            return tokens.access_token

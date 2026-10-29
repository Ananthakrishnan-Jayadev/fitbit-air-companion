import base64
import datetime as dt
import hashlib
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.config import Settings
from fitbit_app.errors import ConfigError, NotConnectedError, OAuthError, ReauthRequiredError
from fitbit_app.ingest.endpoints import AUTH_URL, TOKEN_URL
from fitbit_app.ingest.oauth import (
    TokenManager,
    TokenSet,
    TokenStore,
    build_authorization_url,
    exchange_code,
    new_pkce_pair,
    refresh_access_token,
)
from fitbit_app.ingest.scopes import READ_SCOPES
from fitbit_app.storage.models import OAuthToken
from fixtures.google_api import token_response

NOW = dt.datetime(2026, 10, 29, 12, 0, tzinfo=dt.UTC)


def _tokens(
    access: str = "access-1", refresh: str | None = "refresh-1", expires_in_s: int = 3600
) -> TokenSet:
    return TokenSet(
        access_token=access,
        refresh_token=refresh,
        expires_at=NOW + dt.timedelta(seconds=expires_in_s),
        scope=" ".join(READ_SCOPES),
        token_type="Bearer",
    )


@pytest.fixture
def store(session_factory: sessionmaker[Session], settings: Settings) -> TokenStore:
    return TokenStore(session_factory, settings.fitbit_secret_key)


# --- Authorization URL -------------------------------------------------------------------


def test_pkce_challenge_is_s256_of_verifier() -> None:
    verifier, challenge = new_pkce_pair()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    assert challenge == expected.decode()
    assert 43 <= len(verifier) <= 128


def test_authorization_url(google_settings: Settings) -> None:
    url = build_authorization_url(google_settings, "state-123", "challenge-abc")
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == AUTH_URL
    query = {k: v[0] for k, v in parse_qs(parts.query).items()}
    assert query["client_id"] == "test-client-id"
    assert query["redirect_uri"] == google_settings.google_redirect_uri
    assert query["response_type"] == "code"
    assert query["access_type"] == "offline"
    assert query["state"] == "state-123"
    assert query["code_challenge"] == "challenge-abc"
    assert query["code_challenge_method"] == "S256"
    assert query["scope"].split() == list(READ_SCOPES)


# --- Token endpoint ----------------------------------------------------------------------


@respx.mock
async def test_exchange_code(google_settings: Settings) -> None:
    route = respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=token_response()))
    async with httpx.AsyncClient() as http:
        tokens = await exchange_code(http, google_settings, "code-1", "verifier-1")
    assert tokens.access_token == "access-1"
    assert tokens.refresh_token == "refresh-1"
    form = parse_qs(route.calls.last.request.content.decode())
    assert form["grant_type"] == ["authorization_code"]
    assert form["code_verifier"] == ["verifier-1"]
    assert form["client_secret"] == ["test-client-secret"]


@respx.mock
async def test_exchange_code_failure(google_settings: Settings) -> None:
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    async with httpx.AsyncClient() as http:
        with pytest.raises(OAuthError, match="invalid_grant"):
            await exchange_code(http, google_settings, "bad", "verifier")


@respx.mock
async def test_refresh_rejected_means_reauth(google_settings: Settings) -> None:
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    async with httpx.AsyncClient() as http:
        with pytest.raises(ReauthRequiredError):
            await refresh_access_token(http, google_settings, "refresh-1")


@respx.mock
async def test_refresh_server_error_is_not_reauth(google_settings: Settings) -> None:
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(503))
    async with httpx.AsyncClient() as http:
        with pytest.raises(OAuthError):
            await refresh_access_token(http, google_settings, "refresh-1")


# --- TokenStore --------------------------------------------------------------------------


def test_store_round_trip_encrypts_refresh_token(
    store: TokenStore, session_factory: sessionmaker[Session]
) -> None:
    assert store.load() is None
    store.save(_tokens(), health_user_id="user-1")

    stored = store.load()
    assert stored is not None
    assert stored.access_token == "access-1"
    assert stored.health_user_id == "user-1"
    assert stored.has_refresh_token
    assert store.refresh_token() == "refresh-1"
    with session_factory() as session:
        raw = session.get(OAuthToken, 1)
        assert raw is not None
        assert raw.refresh_token_encrypted is not None
        assert "refresh-1" not in raw.refresh_token_encrypted


def test_save_without_refresh_token_keeps_previous(store: TokenStore) -> None:
    store.save(_tokens(), health_user_id="user-1")
    store.save(_tokens(access="access-2", refresh=None))
    assert store.refresh_token() == "refresh-1"
    stored = store.load()
    assert stored is not None
    assert stored.access_token == "access-2"
    assert stored.health_user_id == "user-1"


def test_needs_reauth_flag_is_cleared_by_save(store: TokenStore) -> None:
    store.save(_tokens())
    store.mark_needs_reauth()
    assert store.load().needs_reauth is True  # type: ignore[union-attr]
    store.save(_tokens(access="access-2"))
    assert store.load().needs_reauth is False  # type: ignore[union-attr]


def test_clear(store: TokenStore) -> None:
    store.save(_tokens())
    store.clear()
    assert store.load() is None
    with pytest.raises(NotConnectedError):
        store.refresh_token()


@pytest.mark.parametrize("key", ["", "not-a-fernet-key"])
def test_bad_secret_key(session_factory: sessionmaker[Session], key: str) -> None:
    with pytest.raises(ConfigError):
        TokenStore(session_factory, SecretStr(key)).save(_tokens())


def test_wrong_key_cannot_decrypt(
    store: TokenStore, session_factory: sessionmaker[Session]
) -> None:
    store.save(_tokens())
    other = TokenStore(session_factory, SecretStr(Fernet.generate_key().decode()))
    with pytest.raises(ReauthRequiredError):
        other.refresh_token()


# --- TokenManager ------------------------------------------------------------------------


async def test_manager_returns_valid_token_without_http(
    store: TokenStore, google_settings: Settings
) -> None:
    store.save(_tokens(expires_in_s=3600))
    async with httpx.AsyncClient() as http:
        manager = TokenManager(store, http, google_settings, clock=lambda: NOW)
        with respx.mock(assert_all_called=False) as router:
            assert await manager.access_token() == "access-1"
            assert router.calls.call_count == 0


@respx.mock
async def test_manager_refreshes_when_expiring(
    store: TokenStore, google_settings: Settings
) -> None:
    store.save(_tokens(expires_in_s=60))  # inside the 2-minute margin
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json=token_response(access="access-2", refresh=None))
    )
    async with httpx.AsyncClient() as http:
        manager = TokenManager(store, http, google_settings, clock=lambda: NOW)
        assert await manager.access_token() == "access-2"
    assert store.load().access_token == "access-2"  # type: ignore[union-attr]
    assert store.refresh_token() == "refresh-1"


@respx.mock
async def test_manager_marks_reauth_on_invalid_grant(
    store: TokenStore, google_settings: Settings
) -> None:
    store.save(_tokens(expires_in_s=0))
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    async with httpx.AsyncClient() as http:
        manager = TokenManager(store, http, google_settings, clock=lambda: NOW)
        with pytest.raises(ReauthRequiredError):
            await manager.access_token()
        # Subsequent calls fail fast without hitting Google again.
        with pytest.raises(ReauthRequiredError):
            await manager.access_token()
    assert respx.calls.call_count == 1


async def test_manager_not_connected(store: TokenStore, google_settings: Settings) -> None:
    async with httpx.AsyncClient() as http:
        with pytest.raises(NotConnectedError):
            await TokenManager(store, http, google_settings).access_token()

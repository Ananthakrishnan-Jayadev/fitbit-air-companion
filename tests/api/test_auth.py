import datetime as dt
from collections.abc import Iterator
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from fitbit_app.config import Settings
from fitbit_app.ingest.endpoints import API_BASE_URL, AUTH_URL, IDENTITY_PATH, REVOKE_URL, TOKEN_URL
from fitbit_app.ingest.oauth import TokenSet
from fitbit_app.ingest.scopes import READ_SCOPES, SLEEP
from fitbit_app.main import create_app
from fixtures.google_api import api_error, token_response

IDENTITY_URL = f"{API_BASE_URL}{IDENTITY_PATH}"


@pytest.fixture
def gclient(google_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(google_settings)) as c:
        yield c


@pytest.fixture
def started(gclient: TestClient, monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    calls: list[dict] = []

    def fake_start(**kwargs: object) -> bool:
        calls.append(kwargs)
        return True

    monkeypatch.setattr(gclient.app.state.sync_service, "start_background", fake_start)
    return calls


def _login_state(client: TestClient) -> str:
    response = client.get("/api/auth/login", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith(AUTH_URL)
    return parse_qs(urlsplit(location).query)["state"][0]


def test_login_requires_configuration(client: TestClient) -> None:
    response = client.get("/api/auth/login", follow_redirects=False)
    assert response.status_code == 400


def test_status_when_not_configured(client: TestClient) -> None:
    body = client.get("/api/auth/status").json()
    assert body["configured"] is False
    assert body["connected"] is False


def test_callback_success(gclient: TestClient, started: list[dict]) -> None:
    state = _login_state(gclient)
    with respx.mock:
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=token_response()))
        respx.get(IDENTITY_URL).mock(
            return_value=httpx.Response(200, json={"healthUserId": "user-1"})
        )
        response = gclient.get(
            f"/api/auth/callback?code=abc&state={state}", follow_redirects=False
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/settings?connected=1"
    assert started == [{}]
    status = gclient.get("/api/auth/status").json()
    assert status["connected"] is True
    assert status["needs_reauth"] is False
    assert status["health_user_id"] == "user-1"
    assert status["missing_scopes"] == []


def test_state_is_single_use(gclient: TestClient, started: list[dict]) -> None:
    state = _login_state(gclient)
    with respx.mock:
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=token_response()))
        respx.get(IDENTITY_URL).mock(return_value=httpx.Response(200, json={"healthUserId": "u"}))
        gclient.get(f"/api/auth/callback?code=abc&state={state}", follow_redirects=False)
        replay = gclient.get(f"/api/auth/callback?code=abc&state={state}", follow_redirects=False)
    assert replay.headers["location"] == "/settings?auth_error=invalid_state"


def test_callback_rejects_unknown_state(gclient: TestClient) -> None:
    response = gclient.get("/api/auth/callback?code=abc&state=forged", follow_redirects=False)
    assert response.headers["location"] == "/settings?auth_error=invalid_state"


def test_callback_user_cancelled(gclient: TestClient) -> None:
    response = gclient.get("/api/auth/callback?error=access_denied", follow_redirects=False)
    assert response.headers["location"] == "/settings?auth_error=access_denied"


def test_callback_account_not_linked(gclient: TestClient, started: list[dict]) -> None:
    state = _login_state(gclient)
    with respx.mock:
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=token_response()))
        respx.get(IDENTITY_URL).mock(
            return_value=httpx.Response(
                400, json=api_error(400, "FAILED_PRECONDITION", "x", "ACCOUNT_NOT_LINKED")
            )
        )
        response = gclient.get(
            f"/api/auth/callback?code=abc&state={state}", follow_redirects=False
        )
    assert response.headers["location"] == "/settings?auth_error=account_not_linked"
    assert gclient.get("/api/auth/status").json()["connected"] is False
    assert started == []


def test_callback_exchange_failure(gclient: TestClient) -> None:
    state = _login_state(gclient)
    with respx.mock:
        respx.post(TOKEN_URL).mock(
            return_value=httpx.Response(400, json={"error": "invalid_grant"})
        )
        response = gclient.get(
            f"/api/auth/callback?code=abc&state={state}", follow_redirects=False
        )
    assert response.headers["location"] == "/settings?auth_error=exchange_failed"


def test_missing_scopes_are_reported(gclient: TestClient) -> None:
    partial = " ".join(s for s in READ_SCOPES if s != SLEEP)
    gclient.app.state.sync_service.token_store.save(
        TokenSet("a", "r", dt.datetime(2030, 1, 1, tzinfo=dt.UTC), partial, "Bearer")
    )
    assert gclient.get("/api/auth/status").json()["missing_scopes"] == [SLEEP]


def test_logout_revokes_and_forgets(gclient: TestClient) -> None:
    gclient.app.state.sync_service.token_store.save(
        TokenSet("a", "r", dt.datetime(2030, 1, 1, tzinfo=dt.UTC), "", "Bearer")
    )
    with respx.mock:
        revoke = respx.post(REVOKE_URL).mock(return_value=httpx.Response(200))
        response = gclient.post("/api/auth/logout")
    assert response.status_code == 204
    assert revoke.called
    assert gclient.get("/api/auth/status").json()["connected"] is False

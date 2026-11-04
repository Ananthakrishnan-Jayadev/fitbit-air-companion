from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from fitbit_app.config import Settings
from fitbit_app.login import COOKIE_NAME, MAX_FAILURES
from fitbit_app.main import create_app

PASSWORD = "correct horse"


@pytest.fixture
def protected_client(settings: Settings) -> Iterator[TestClient]:
    protected = settings.model_copy(update={"app_password": SecretStr(PASSWORD)})
    with TestClient(create_app(protected)) as test_client:
        yield test_client


def _login(client: TestClient, password: str = PASSWORD) -> int:
    return client.post("/api/session/login", json={"password": password}).status_code


# --- Login disabled (no APP_PASSWORD): unchanged behaviour ---------------------------------


def test_no_password_means_no_login(client: TestClient) -> None:
    assert client.get("/api/session").json() == {"required": False, "authenticated": True}
    assert client.get("/api/profile").status_code == 200


def test_login_endpoint_404_when_disabled(client: TestClient) -> None:
    assert _login(client) == 404


# --- Login enabled --------------------------------------------------------------------------


def test_api_requires_session(protected_client: TestClient) -> None:
    assert protected_client.get("/api/session").json() == {
        "required": True,
        "authenticated": False,
    }
    response = protected_client.get("/api/profile")
    assert response.status_code == 401
    assert response.json() == {"detail": "Login required"}
    assert protected_client.post("/api/sync", json={}).status_code == 401


def test_public_paths_stay_open(protected_client: TestClient) -> None:
    assert protected_client.get("/api/health").status_code == 200
    # The UI shell holds no data; it shows the login form when the API says 401.
    assert protected_client.get("/").status_code in {200, 503}


def test_wrong_password(protected_client: TestClient) -> None:
    response = protected_client.post("/api/session/login", json={"password": "nope"})
    assert response.status_code == 401
    assert COOKIE_NAME not in response.cookies
    assert protected_client.get("/api/profile").status_code == 401


def test_login_sets_cookie_and_unlocks_api(protected_client: TestClient) -> None:
    response = protected_client.post("/api/session/login", json={"password": PASSWORD})
    assert response.status_code == 204
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "max-age=2592000" in cookie

    assert protected_client.get("/api/session").json()["authenticated"] is True
    assert protected_client.get("/api/profile").status_code == 200


def test_forged_cookie_rejected(protected_client: TestClient) -> None:
    protected_client.cookies.set(COOKIE_NAME, "1800000000.deadbeef")
    assert protected_client.get("/api/profile").status_code == 401


def test_logout_clears_session(protected_client: TestClient) -> None:
    assert _login(protected_client) == 204
    assert protected_client.post("/api/session/logout").status_code == 204
    assert protected_client.get("/api/profile").status_code == 401


def test_throttle_after_repeated_failures(protected_client: TestClient) -> None:
    for _ in range(MAX_FAILURES):
        assert _login(protected_client, "nope") == 401
    # Even the right password is refused until the window passes.
    assert _login(protected_client) == 429


def test_password_never_logged(
    protected_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    _login(protected_client, "wrong-guess-123")
    _login(protected_client)
    assert "wrong-guess-123" not in caplog.text
    assert PASSWORD not in caplog.text


def test_warns_when_exposed_without_password(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    create_app(settings.model_copy(update={"host": "0.0.0.0"}))
    assert "without a login" in caplog.text


def test_no_warning_on_loopback(settings: Settings, caplog: pytest.LogCaptureFixture) -> None:
    create_app(settings)
    assert "without a login" not in caplog.text

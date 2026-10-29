from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.exc import OperationalError

from fitbit_app import __version__
from fitbit_app.ai.status import OllamaStatus
from fitbit_app.api import health as health_module
from fitbit_app.config import Settings
from fitbit_app.main import create_app


def _ollama(reachable: bool, present: bool) -> OllamaStatus:
    return OllamaStatus(reachable=reachable, model="gemma4:31b", model_present=present)


@pytest.fixture
def ai_client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings.model_copy(update={"ai_enabled": True}))) as c:
        yield c


def test_health_ok_with_ai_disabled(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["database"]["ok"] is True
    assert body["ai_enabled"] is False
    assert body["ollama"] is None
    assert body["google"] == {"configured": False}


def test_health_ok_when_ollama_ready(
    ai_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_check(host: str, model: str) -> OllamaStatus:
        return _ollama(reachable=True, present=True)

    monkeypatch.setattr(health_module, "check_ollama", fake_check)
    body = ai_client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["ollama"]["model_present"] is True


@pytest.mark.parametrize(("reachable", "present"), [(False, False), (True, False)])
def test_health_degraded_when_ollama_not_ready(
    ai_client: TestClient, monkeypatch: pytest.MonkeyPatch, reachable: bool, present: bool
) -> None:
    async def fake_check(host: str, model: str) -> OllamaStatus:
        return _ollama(reachable=reachable, present=present)

    monkeypatch.setattr(health_module, "check_ollama", fake_check)
    body = ai_client.get("/api/health").json()
    assert body["status"] == "degraded"
    assert body["database"]["ok"] is True


def test_health_degraded_when_database_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_ping(engine: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("disk I/O error"))

    monkeypatch.setattr(health_module, "ping", broken_ping)
    body = client.get("/api/health").json()
    assert body["status"] == "degraded"
    assert body["database"] == {"ok": False, "detail": "Database unavailable"}


def test_google_configured_flag(settings: Settings) -> None:
    configured = settings.model_copy(
        update={"google_client_id": "id", "google_client_secret": SecretStr("secret")}
    )
    with TestClient(create_app(configured)) as c:
        assert c.get("/api/health").json()["google"] == {"configured": True}


def test_startup_creates_and_migrates_database(client: TestClient, settings: Settings) -> None:
    assert settings.db_path.is_file()

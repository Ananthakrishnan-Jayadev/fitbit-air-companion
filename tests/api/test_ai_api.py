import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from fitbit_app.ai.status import OllamaStatus
from fitbit_app.api import ai as ai_module
from fitbit_app.config import Settings
from fitbit_app.main import create_app
from fixtures.fake_llm import FakeLLM
from fixtures.scenario import LAST, build_scored_db


@pytest.fixture
def ai_client(settings: Settings) -> Iterator[TestClient]:
    enabled = settings.model_copy(update={"ai_enabled": True})
    with TestClient(create_app(enabled)) as c:
        build_scored_db(c.app.state.session_factory)
        c.app.state.ai_service.llm = FakeLLM()
        yield c


def _events(body: str) -> list[dict]:
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


def test_status_when_disabled(client: TestClient) -> None:
    body = client.get("/api/ai/status").json()
    assert body["enabled"] is False
    assert "disabled" in body["detail"]


def test_status_when_enabled(ai_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_check(host: str, model: str) -> OllamaStatus:
        return OllamaStatus(reachable=True, model=model, model_present=True)

    monkeypatch.setattr(ai_module, "check_ollama", fake_check)
    body = ai_client.get("/api/ai/status").json()
    assert body["enabled"] is True
    assert body["model_present"] is True
    assert body["busy"] is False


def test_insights_without_data(client: TestClient) -> None:
    assert client.get("/api/ai/insights").json()["date"] is None


def test_insights_after_generation(ai_client: TestClient) -> None:
    portal_service = ai_client.app.state.ai_service
    ai_client.portal.call(portal_service.generate, "daily_brief", LAST)  # type: ignore[union-attr]
    body = ai_client.get("/api/ai/insights").json()
    assert body["date"] == LAST.isoformat()
    assert body["daily_brief"]["content"]["headline"] == "Recovery is solid today."
    assert body["anomaly"] is None


def test_generate_when_disabled(client: TestClient) -> None:
    assert client.post("/api/ai/generate", json={}).status_code == 503


@pytest.mark.parametrize(("accepted", "status_code"), [(True, 202), (False, 409)])
def test_generate(
    ai_client: TestClient, monkeypatch: pytest.MonkeyPatch, accepted: bool, status_code: int
) -> None:
    calls: list[tuple] = []

    def fake_start(kind: str, day: object) -> bool:
        calls.append((kind, day))
        return accepted

    monkeypatch.setattr(ai_client.app.state.ai_service, "start_generate", fake_start)
    response = ai_client.post("/api/ai/generate", json={"kind": "weekly_review"})
    assert response.status_code == status_code
    assert calls == [("weekly_review", LAST)]


def test_chat_streams_server_sent_events(ai_client: TestClient) -> None:
    response = ai_client.post("/api/ai/chat", json={"message": "How did I sleep?"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response.text)
    conversation_id = events[0]["conversation_id"]
    assert "".join(e["delta"] for e in events if "delta" in e) == "You slept well."
    assert events[-1] == {"done": True}

    history = ai_client.get(f"/api/ai/chat/{conversation_id}").json()
    assert [m["role"] for m in history] == ["user", "assistant"]


def test_chat_rejects_empty_message(ai_client: TestClient) -> None:
    assert ai_client.post("/api/ai/chat", json={"message": ""}).status_code == 422


def test_chat_when_disabled(client: TestClient) -> None:
    assert client.post("/api/ai/chat", json={"message": "hi"}).status_code == 503

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from fitbit_app.ingest.oauth import TokenSet
from fitbit_app.ingest.registry import select_specs


def _connect(client: TestClient) -> None:
    client.app.state.sync_service.token_store.save(
        TokenSet("a", "r", dt.datetime(2030, 1, 1, tzinfo=dt.UTC), "", "Bearer")
    )


def test_status_lists_every_type(client: TestClient) -> None:
    body = client.get("/api/sync/status").json()
    assert body["running"] is False
    assert body["last_run"] is None
    assert [t["key"] for t in body["types"]] == [s.key for s in select_specs(include_beta=False)]
    assert all(t["last_success_at"] is None for t in body["types"])


def test_trigger_requires_connection(client: TestClient) -> None:
    response = client.post("/api/sync", json={})
    assert response.status_code == 400
    assert "not connected" in response.json()["detail"]


def test_trigger_rejects_unknown_types(client: TestClient) -> None:
    response = client.post("/api/sync", json={"types": ["nope"]})
    assert response.status_code == 400


@pytest.mark.parametrize(("accepted", "status_code"), [(True, 202), (False, 409)])
def test_trigger(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, accepted: bool, status_code: int
) -> None:
    _connect(client)
    calls: list[dict] = []

    def fake_start(**kwargs: object) -> bool:
        calls.append(kwargs)
        return accepted

    monkeypatch.setattr(client.app.state.sync_service, "start_background", fake_start)
    response = client.post("/api/sync", json={"types": ["steps"], "since": "2026-09-01"})
    assert response.status_code == status_code
    assert calls == [{"keys": ["steps"], "since": dt.date(2026, 9, 1)}]

import datetime as dt
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from fitbit_app.config import Settings
from fitbit_app.journal import PRESET_TAGS, normalize_tags
from fitbit_app.main import create_app
from fitbit_app.storage.models import Score
from fitbit_app.storage.types import utcnow

DAY = "2026-10-01"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (["Alcohol", "alcohol", " Late Meal "], ["alcohol", "late_meal"]),
        (["", "  ", "!!"], []),
        (["x" * 50], ["x" * 30]),
        (["Coffee @ 4pm"], ["coffee_4pm"]),
    ],
)
def test_normalize_tags(raw: list[str], expected: list[str]) -> None:
    assert normalize_tags(raw) == expected


def test_save_read_and_delete(client: TestClient) -> None:
    body = {"tags": ["Alcohol", "late meal"], "note": " ok "}
    saved = client.put(f"/api/journal/{DAY}", json=body)
    assert saved.json() == {"date": DAY, "tags": ["alcohol", "late_meal"], "note": "ok"}

    listed = client.get(f"/api/journal?start={DAY}&end={DAY}").json()
    assert listed == [saved.json()]

    assert client.delete(f"/api/journal/{DAY}").status_code == 204
    assert client.get(f"/api/journal?start={DAY}&end={DAY}").json() == []


def test_empty_entry_is_removed(client: TestClient) -> None:
    client.put(f"/api/journal/{DAY}", json={"tags": ["nap"]})
    client.put(f"/api/journal/{DAY}", json={"tags": [], "note": "  "})
    assert client.get(f"/api/journal?start={DAY}&end={DAY}").json() == []


def test_tags_include_presets_and_custom(client: TestClient) -> None:
    client.put(f"/api/journal/{DAY}", json={"tags": ["alcohol", "cold_plunge"]})
    tags = {t["tag"]: t for t in client.get("/api/journal/tags").json()}
    assert set(PRESET_TAGS) <= set(tags)
    assert tags["alcohol"] == {"tag": "alcohol", "count": 1, "preset": True}
    assert tags["cold_plunge"] == {"tag": "cold_plunge", "count": 1, "preset": False}


def test_journal_rejects_bad_range(client: TestClient) -> None:
    assert client.get("/api/journal?start=2026-10-02&end=2026-10-01").status_code == 400


@pytest.fixture
def journal_client(settings: Settings) -> Iterator[TestClient]:
    """30 tagged days: 'alcohol' every third day, followed by lower recovery."""
    with TestClient(create_app(settings)) as c:
        with c.app.state.session_factory() as session:
            start = dt.date(2026, 9, 1)
            for i in range(30):
                day = start + dt.timedelta(days=i)
                drank = i % 3 == 0
                c.put(
                    f"/api/journal/{day}",
                    json={"tags": ["alcohol"] if drank else ["early_bedtime"]},
                )
                session.add(
                    Score(
                        date=day + dt.timedelta(days=1),
                        recovery=45.0 + (i % 2) if drank else 70.0 + (i % 2),
                        computed_at=utcnow(),
                    )
                )
            session.commit()
        yield c


def test_correlations(journal_client: TestClient) -> None:
    body = journal_client.get("/api/correlations?outcome=recovery&days=60&end=2026-10-01").json()
    assert body["logged_days"] == 30
    effects = {e["tag"]: e for e in body["effects"]}
    assert effects["alcohol"]["difference"] < -20
    assert effects["alcohol"]["confident"] is True


def test_correlations_rejects_unknown_outcome(client: TestClient) -> None:
    assert client.get("/api/correlations?outcome=mood").status_code == 422

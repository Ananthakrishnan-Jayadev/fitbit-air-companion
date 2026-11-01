import datetime as dt
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from fitbit_app.config import Settings
from fitbit_app.main import create_app
from fitbit_app.storage.models import DailyMetric
from fitbit_app.storage.types import utcnow

LAST = dt.date(2026, 10, 31)


@pytest.fixture
def body_client(settings: Settings) -> Iterator[TestClient]:
    """Weigh-ins every 3 days for 60 days, losing 0.1 kg each time; body fat on some days."""
    with TestClient(create_app(settings)) as c:
        with c.app.state.session_factory() as session:
            for i, days_ago in enumerate(range(60, -1, -3)):
                day = LAST - dt.timedelta(days=days_ago)
                session.add(
                    DailyMetric(
                        date=day,
                        weight_kg=round(82.0 - 0.1 * i, 2),
                        body_fat_pct=20.0 if days_ago % 6 == 0 else None,
                        updated_at=utcnow(),
                    )
                )
            # A day with other data but no weigh-in must not show up as a point.
            yesterday = LAST - dt.timedelta(days=1)
            session.add(DailyMetric(date=yesterday, steps=9000, updated_at=utcnow()))
            session.commit()
        yield c


def test_body_summary(body_client: TestClient) -> None:
    body = body_client.get("/api/body?days=30").json()
    assert body["latest_date"] == LAST.isoformat()
    assert body["weight_kg"] == 80.0
    assert body["body_fat_pct"] == 20.0
    assert body["fat_mass_kg"] == 16.0
    assert body["lean_mass_kg"] == 64.0
    assert body["weight_change_7d"] == -0.3  # vs the reading 9 days earlier
    assert body["weight_change_30d"] == -1.0
    assert all(p["date"] >= (LAST - dt.timedelta(days=29)).isoformat() for p in body["points"])
    assert all(p["weight_kg"] is not None or p["body_fat_pct"] is not None for p in body["points"])


def test_body_without_weigh_ins(client: TestClient) -> None:
    body = client.get("/api/body").json()
    assert body["latest_date"] is None
    assert body["points"] == []


def test_weight_trend(body_client: TestClient) -> None:
    trend = body_client.get(f"/api/trends?metric=weight_kg&days=30&end={LAST}").json()
    values = [p["value"] for p in trend["points"] if p["value"] is not None]
    assert values[-1] == 80.0

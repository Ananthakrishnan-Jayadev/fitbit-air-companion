import datetime as dt
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from fitbit_app.config import Settings
from fitbit_app.main import create_app
from fitbit_app.scoring import ScoreService
from fixtures.db_seed import seed
from fixtures.synthetic import SyntheticData, generate

START = dt.date(2026, 9, 1)
DAYS = 21
SICK = START + dt.timedelta(days=18)
LAST = START + dt.timedelta(days=DAYS - 1)
NOW = dt.datetime.combine(START + dt.timedelta(days=DAYS), dt.time(), tzinfo=dt.UTC)


@pytest.fixture(scope="module")
def data() -> SyntheticData:
    return generate(START, DAYS, seed=5, sick_days={SICK})


@pytest.fixture
def scored(settings: Settings, data: SyntheticData) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        session_factory = c.app.state.session_factory
        seed(session_factory, data)
        ScoreService(session_factory, clock=lambda: NOW).recompute_all()
        yield c


# --- /api/today, /api/daily, /api/trends -------------------------------------------------


def test_today_needs_scores(client: TestClient) -> None:
    assert client.get("/api/today").status_code == 404


def test_today_defaults_to_latest_day(scored: TestClient) -> None:
    body = scored.get("/api/today").json()
    assert body["date"] == LAST.isoformat()
    assert body["first_date"] == START.isoformat()
    assert body["last_date"] == LAST.isoformat()
    assert 0 <= body["recovery"] <= 100
    assert 0 <= body["sleep_perf"] <= 100
    assert body["strain_target"] is not None
    assert body["metrics"]["resting_hr"] > 0
    band = body["baselines"]["resting_hr"]
    assert band["low"] < band["typical"] < band["high"]
    assert "recovery" in body["components"]
    assert "flags" not in body["components"]


def test_today_for_a_sick_day(scored: TestClient) -> None:
    body = scored.get(f"/api/today?date={SICK.isoformat()}").json()
    assert "illness_watch" in body["flags"]
    assert body["z"]["resting_hr"] > 2


def test_daily_range(scored: TestClient) -> None:
    rows = scored.get(f"/api/daily?start={START}&end={LAST}").json()
    assert [r["date"] for r in rows] == [
        (START + dt.timedelta(days=i)).isoformat() for i in range(DAYS)
    ]
    assert rows[-1]["scores"]["recovery"] is not None
    assert rows[-1]["metrics"]["steps"] > 0


def test_daily_rejects_bad_range(scored: TestClient) -> None:
    assert scored.get(f"/api/daily?start={LAST}&end={START}").status_code == 400


def test_trends_with_baseline_band(scored: TestClient) -> None:
    body = scored.get("/api/trends?metric=resting_hr&days=30").json()
    assert body["metric"] == "resting_hr"
    assert len(body["points"]) == DAYS
    assert body["points"][0]["baseline"] is None  # no history yet
    assert body["points"][-1]["baseline"] is not None


def test_trends_for_scores(scored: TestClient) -> None:
    body = scored.get("/api/trends?metric=recovery&days=30").json()
    assert any(p["value"] is not None for p in body["points"])
    assert all(p["baseline"] is None for p in body["points"])


def test_trends_rejects_unknown_metric(scored: TestClient) -> None:
    assert scored.get("/api/trends?metric=nope").status_code == 422


# --- /api/heart, /api/sleep, /api/activity, /api/exercise --------------------------------


def test_heart(scored: TestClient) -> None:
    body = scored.get(f"/api/heart?date={LAST}&points=300").json()
    assert body["sample_count"] == 1440  # synthetic data: one sample per minute
    assert len(body["samples"]) == 300
    timestamps = [t for t, _ in body["samples"]]
    assert timestamps == sorted(timestamps)
    assert body["min_bpm"] < body["max_bpm"]
    assert body["utc_offset_min"] == 0
    assert body["zones"] == []  # no raw zone data in the synthetic set
    # Epoch milliseconds, i.e. within the requested day (not seconds or microseconds).
    day_start = dt.datetime.combine(LAST, dt.time(), tzinfo=dt.UTC).timestamp() * 1000
    assert all(day_start - 86_400_000 <= t <= day_start + 2 * 86_400_000 for t in timestamps)


def test_heart_window_returns_only_that_span(scored: TestClient) -> None:
    day = scored.get(f"/api/heart?date={LAST}&points=300").json()
    first = day["samples"][0][0]
    start, end = first + 3_600_000, first + 2 * 3_600_000  # one hour, in epoch ms
    body = scored.get(f"/api/heart?date={LAST}&points=5000&start_ms={start}&end_ms={end}").json()
    times = [t for t, _ in body["samples"]]
    assert times and all(start <= t <= end for t in times)
    # One reading per minute in the synthetic set: the full hour, not a simplified subset.
    assert body["sample_count"] == len(times) == 61
    # Daily stats still describe the whole day.
    assert (body["min_bpm"], body["max_bpm"]) == (day["min_bpm"], day["max_bpm"])


def test_heart_window_outside_the_day_is_empty(scored: TestClient) -> None:
    body = scored.get(f"/api/heart?date={LAST}&start_ms=0&end_ms=1000").json()
    assert body["samples"] == []
    assert body["sample_count"] == 0


@pytest.mark.parametrize("query", ["start_ms=1000", "end_ms=1000", "start_ms=2000&end_ms=1000"])
def test_heart_window_validation(scored: TestClient, query: str) -> None:
    assert scored.get(f"/api/heart?date={LAST}&{query}").status_code == 422


def test_sleep(scored: TestClient) -> None:
    body = scored.get(f"/api/sleep?date={LAST}").json()
    assert body["night"] is not None
    assert body["stages"]
    assert {"light", "deep", "rem"} <= set(body["stage_minutes"])
    assert body["spo2"] and body["hrv"]
    assert body["score"] is not None
    assert "components" in body["components"]


def test_sleep_range(scored: TestClient) -> None:
    nights = scored.get(f"/api/sleep/range?start={START}&end={LAST}").json()
    assert len(nights) == DAYS
    assert len(nights[0]["bedtime_local"]) == 5  # HH:MM
    assert nights[-1]["asleep_min"] > 0


def test_activity(scored: TestClient) -> None:
    body = scored.get(f"/api/activity?date={LAST}").json()
    assert len(body["hourly"]) == 24
    assert sum(h["steps"] for h in body["hourly"]) == body["totals"]["steps"]
    assert "SEDENTARY" in body["level_minutes"]
    assert body["stress"]
    assert all(0 <= v <= 100 for _, v in body["stress"])


def test_exercise_range(scored: TestClient, data: SyntheticData) -> None:
    workouts = scored.get(f"/api/exercise?start={START}&end={LAST}").json()
    assert len(workouts) == len(data.workouts)
    assert all(w["max_hr"] is not None for w in workouts)


@pytest.mark.parametrize("path", ["/api/heart", "/api/sleep", "/api/activity"])
def test_details_need_scores(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404

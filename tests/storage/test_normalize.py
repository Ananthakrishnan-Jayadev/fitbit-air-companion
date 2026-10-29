import datetime as dt
from collections.abc import Iterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.ingest.registry import REGISTRY, DataTypeSpec
from fitbit_app.storage.models import (
    ActivityMinute,
    DailyMetric,
    DataPoint,
    ExerciseSession,
    HrSample,
    HrvSample,
    SleepSession,
    SleepStage,
    Spo2Sample,
)
from fitbit_app.storage.normalize import store_points
from fixtures import google_api as g

UTC = dt.UTC


def _spec(key: str) -> DataTypeSpec:
    return next(s for s in REGISTRY if s.key == key)


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as s:
        yield s


def _store(session: Session, key: str, points: list[dict]) -> int:
    result = store_points(session, _spec(key), points)
    session.commit()
    return result.count


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_heart_rate_is_typed_only(session: Session) -> None:
    points = [
        g.heart_rate("2026-10-01T12:00:00Z", 61),
        g.heart_rate("2026-10-01T12:00:01Z", 95, motion="ACTIVE"),
    ]
    assert _store(session, "heart-rate", points) == 2
    rows = session.scalars(select(HrSample).order_by(HrSample.ts)).all()
    assert [(r.bpm, r.motion_context) for r in rows] == [(61, "SEDENTARY"), (95, "ACTIVE")]
    assert _count(session, DataPoint) == 0


def test_storing_twice_is_idempotent(session: Session) -> None:
    points = [g.steps("2026-10-01T12:00:00Z", "2026-10-01T12:01:00Z", 80)]
    _store(session, "steps", points)
    _store(session, "steps", points)
    assert _count(session, DataPoint) == 1
    assert _count(session, ActivityMinute) == 1


def test_hrv_and_spo2(session: Session) -> None:
    _store(session, "heart-rate-variability", [g.hrv("2026-10-01T06:00:00Z", 48.5)])
    _store(session, "oxygen-saturation", [g.spo2("2026-10-01T06:00:00Z", 96.4)])
    assert session.scalar(select(HrvSample.rmssd_ms)) == 48.5
    assert session.scalar(select(Spo2Sample.spo2_pct)) == 96.4


def test_interval_types_merge_into_one_minute_row(session: Session) -> None:
    start, end = "2026-10-01T12:00:30Z", "2026-10-01T12:01:00Z"
    _store(session, "steps", [g.steps(start, end, 80)])
    _store(session, "distance", [g.distance(start, end, 61000)])
    row = session.scalars(select(ActivityMinute)).one()
    assert row.ts == dt.datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    assert row.steps == 80
    assert row.distance_m == 61.0


def test_activity_level_covers_every_minute(session: Session) -> None:
    _store(
        session,
        "activity-level",
        [g.activity_level("2026-10-01T12:00:00Z", "2026-10-01T12:03:00Z", "MODERATE")],
    )
    levels = session.scalars(select(ActivityMinute.activity_level)).all()
    assert levels == ["MODERATE"] * 3


def test_sleep_session_and_stages(session: Session) -> None:
    # 23:00 EDT Sep 30 -> 06:30 EDT Oct 1: belongs to Oct 1 (wake date, local time).
    point = g.sleep(
        "2026-10-01T03:00:00Z",
        "2026-10-01T10:30:00Z",
        [
            ("2026-10-01T03:00:00Z", "2026-10-01T05:00:00Z", "LIGHT"),
            ("2026-10-01T05:00:00Z", "2026-10-01T06:00:00Z", "DEEP"),
            ("2026-10-01T06:00:00Z", "2026-10-01T10:30:00Z", "REM"),
        ],
        minutes_in_period=450,
        minutes_asleep=405,
    )
    _store(session, "sleep", [point])
    sleep = session.scalars(select(SleepSession)).one()
    assert sleep.local_date == dt.date(2026, 10, 1)
    assert sleep.duration_min == 450
    assert sleep.efficiency == pytest.approx(90.0)
    assert sleep.is_main is True
    stages = session.scalars(select(SleepStage.stage).order_by(SleepStage.start_ts)).all()
    assert stages == ["light", "deep", "rem"]


def test_sleep_local_date_uses_offset_not_utc(session: Session) -> None:
    # Ends 22:00 EDT Oct 1 = 02:00 UTC Oct 2: still Oct 1 locally.
    point = g.sleep("2026-10-01T23:00:00Z", "2026-10-02T02:00:00Z", [], name="nap-1", main=False)
    _store(session, "sleep", [point])
    sleep = session.scalars(select(SleepSession)).one()
    assert sleep.local_date == dt.date(2026, 10, 1)
    assert sleep.is_main is False
    assert sleep.duration_min == 180  # from the interval when no summary


def test_resynced_sleep_replaces_stages(session: Session) -> None:
    start, end = "2026-10-01T03:00:00Z", "2026-10-01T04:00:00Z"
    _store(session, "sleep", [g.sleep(start, end, [(start, end, "LIGHT")])])
    revised = [(start, "2026-10-01T03:30:00Z", "DEEP"), ("2026-10-01T03:30:00Z", end, "REM")]
    _store(session, "sleep", [g.sleep(start, end, revised)])
    assert _count(session, SleepSession) == 1
    stages = session.scalars(select(SleepStage.stage).order_by(SleepStage.start_ts)).all()
    assert stages == ["deep", "rem"]


def test_exercise(session: Session) -> None:
    point = g.exercise("2026-10-01T22:00:00Z", "2026-10-01T22:50:00Z", "RUNNING", "2700s")
    _store(session, "exercise", [point])
    row = session.scalars(select(ExerciseSession)).one()
    assert row.activity_type == "RUNNING"
    assert row.duration_min == 45
    assert row.local_date == dt.date(2026, 10, 1)


def test_daily_types_merge_into_daily_metrics(session: Session) -> None:
    day = dt.date(2026, 10, 1)
    _store(
        session,
        "daily-resting-heart-rate",
        [g.daily("dailyRestingHeartRate", day, beatsPerMinute="57")],
    )
    spo2 = g.daily("dailyOxygenSaturation", day, averagePercentage=96.1, lowerBoundPercentage=92.0)
    _store(session, "daily-oxygen-saturation", [spo2])
    _store(
        session,
        "daily-sleep-temperature-derivations",
        [
            g.daily(
                "dailySleepTemperatureDerivations",
                day,
                nightlyTemperatureCelsius=34.9,
                baselineTemperatureCelsius=34.5,
            )
        ],
    )
    breathing = g.daily("dailyRespiratoryRate", day, breathsPerMinute=14.2)
    _store(session, "daily-respiratory-rate", [breathing])
    row = session.get(DailyMetric, day)
    assert row is not None
    assert row.resting_hr == 57
    assert row.spo2_avg == 96.1
    assert row.spo2_min == 92.0
    assert row.skin_temp_delta_c == pytest.approx(0.4)
    assert row.respiratory_rate == 14.2


def test_temperature_without_baseline_is_skipped(session: Session) -> None:
    day = dt.date(2026, 10, 1)
    point = g.daily("dailySleepTemperatureDerivations", day, nightlyTemperatureCelsius=34.9)
    _store(session, "daily-sleep-temperature-derivations", [point])
    assert session.get(DailyMetric, day) is None
    assert _count(session, DataPoint) == 1  # raw is still kept


def test_steps_rollup(session: Session) -> None:
    day = dt.date(2026, 10, 1)
    _store(session, "steps:daily", [g.rollup_steps(day, 9876)])
    row = session.get(DailyMetric, day)
    assert row is not None
    assert row.steps == 9876
    assert session.scalar(select(DataPoint.data_type)) == "steps:daily"


def test_points_without_body_are_skipped(session: Session) -> None:
    good = g.steps("2026-10-01T12:00:00Z", "2026-10-01T12:01:00Z", 10)
    assert _store(session, "steps", [good, {"dataPointName": "x"}]) == 1


def test_result_reports_earliest_start(session: Session) -> None:
    result = store_points(
        session,
        _spec("heart-rate"),
        [g.heart_rate("2026-10-01T12:00:05Z", 60), g.heart_rate("2026-10-01T12:00:01Z", 60)],
    )
    assert result.earliest == dt.datetime(2026, 10, 1, 12, 0, 1, tzinfo=UTC)

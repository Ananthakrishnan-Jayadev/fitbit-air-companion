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
from fitbit_app.storage.normalize import renormalize, store_points
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


def test_main_sleep_records_wake_up_offset(session: Session) -> None:
    start, end = "2026-10-01T03:00:00Z", "2026-10-01T10:30:00Z"
    _store(session, "sleep", [g.sleep(start, end, [(start, end, "LIGHT")])])
    row = session.get(DailyMetric, dt.date(2026, 10, 1))
    assert row is not None
    assert row.tz_offset_min == -240


def test_nap_does_not_set_offset(session: Session) -> None:
    point = g.sleep("2026-10-01T18:00:00Z", "2026-10-01T19:00:00Z", [], name="nap", main=False)
    _store(session, "sleep", [point])
    assert session.get(DailyMetric, dt.date(2026, 10, 1)) is None


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
    metrics = {
        "caloriesKcal": 410,
        "distanceMillimeters": 5200000,
        "averageHeartRateBeatsPerMinute": "148",
        "activeZoneMinutes": "38",
        "heartRateZoneDurations": {
            "lightTime": "300s",
            "moderateTime": "1200s",
            "vigorousTime": "900s",
            "peakTime": "60s",
        },
    }
    point = g.exercise("2026-10-01T22:00:00Z", "2026-10-01T22:50:00Z", "RUNNING", "2700s", metrics)
    _store(session, "exercise", [point])
    row = session.scalars(select(ExerciseSession)).one()
    assert row.activity_type == "RUNNING"
    assert row.duration_min == 45
    assert row.local_date == dt.date(2026, 10, 1)
    assert row.calories == 410
    assert row.distance_m == 5200
    assert row.avg_hr == 148
    assert row.max_hr is None
    assert row.zones_json == {
        "light_min": 5,
        "moderate_min": 20,
        "vigorous_min": 15,
        "peak_min": 1,
        "active_zone_minutes": 38,
    }


def test_exercise_without_metrics(session: Session) -> None:
    point = g.exercise("2026-10-01T22:00:00Z", "2026-10-01T22:30:00Z", "WALKING")
    _store(session, "exercise", [point])
    row = session.scalars(select(ExerciseSession)).one()
    assert row.duration_min == 30
    assert row.calories is None
    assert row.zones_json is None


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


def test_daily_rollup_totals(session: Session) -> None:
    day = dt.date(2026, 10, 1)
    _store(session, "distance:daily", [g.rollup(day, "distance", millimetersSum="7350000")])
    _store(session, "total-calories:daily", [g.rollup(day, "totalCalories", kcalSum=2310.5)])
    _store(
        session, "active-energy-burned:daily", [g.rollup(day, "activeEnergyBurned", kcalSum=640.0)]
    )
    azm = g.rollup(
        day,
        "activeZoneMinutes",
        sumInFatBurnHeartZone="20",
        sumInCardioHeartZone="12",
        sumInPeakHeartZone="4",
    )
    _store(session, "active-zone-minutes:daily", [azm])
    row = session.get(DailyMetric, day)
    assert row is not None
    assert row.distance_m == 7350
    assert row.total_calories == 2310.5
    assert row.active_calories == 640.0
    assert row.active_zone_minutes == 36


def test_renormalize_rebuilds_typed_rows_from_raw(session: Session) -> None:
    day = dt.date(2026, 10, 1)
    _store(session, "total-calories:daily", [g.rollup(day, "totalCalories", kcalSum=2000.0)])
    session.query(DailyMetric).delete()
    session.commit()

    assert renormalize(session, _spec("total-calories:daily")) == 1
    session.commit()
    row = session.get(DailyMetric, day)
    assert row is not None
    assert row.total_calories == 2000.0


def test_renormalize_skips_types_without_raw(session: Session) -> None:
    _store(session, "heart-rate", [g.heart_rate("2026-10-01T12:00:00Z", 60)])
    assert renormalize(session, _spec("heart-rate")) == 0


def test_weight_keeps_the_latest_reading_of_the_local_day(session: Session) -> None:
    # Newest page first, like the API: the later reading must win regardless of order.
    _store(session, "weight", [g.weight("2026-10-01T22:00:00Z", 80.4)])  # 18:00 EDT Oct 1
    _store(session, "weight", [g.weight("2026-10-01T11:00:00Z", 79.6)])  # 07:00 EDT Oct 1
    # 01:00 UTC Oct 2 is still Oct 1 (21:00) in EDT and is the latest reading of that day.
    _store(session, "weight", [g.weight("2026-10-02T01:00:00Z", 80.9)])
    row = session.get(DailyMetric, dt.date(2026, 10, 1))
    assert row is not None
    assert row.weight_kg == 80.9
    assert session.get(DailyMetric, dt.date(2026, 10, 2)) is None


def test_body_fat(session: Session) -> None:
    _store(session, "body-fat", [g.body_fat("2026-10-01T11:00:00Z", 18.4)])
    row = session.get(DailyMetric, dt.date(2026, 10, 1))
    assert row is not None
    assert row.body_fat_pct == 18.4


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

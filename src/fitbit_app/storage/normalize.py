"""Store one page of API data points: raw JSON (data_points) + typed tables.

Field names follow the DataPoint reference
(https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints), and were
checked against live responses on 2026-10-29. Raw JSON is kept, so `renormalize` can rebuild
the typed tables after a mapping change without re-downloading.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fitbit_app.ingest.registry import DataTypeSpec, RecordKind
from fitbit_app.ingest.timeutil import (
    floor_minute,
    parse_date,
    parse_duration_minutes,
    parse_offset,
    parse_ts,
    start_of_day_utc,
)
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
from fitbit_app.storage.types import utcnow
from fitbit_app.storage.upsert import upsert

logger = logging.getLogger(__name__)

Point = dict[str, Any]


@dataclass(frozen=True)
class StoreResult:
    count: int
    earliest: dt.datetime | None


def store_points(session: Session, spec: DataTypeSpec, points: list[Point]) -> StoreResult:
    """Persist a page of points for `spec`. Caller commits."""
    usable = [p for p in points if isinstance(p.get(spec.field), dict)]
    skipped = len(points) - len(usable)
    if skipped:
        logger.warning("%s: skipped %d points without a '%s' body", spec.key, skipped, spec.field)
    if not usable:
        return StoreResult(0, None)

    bounds = [point_bounds(spec, p) for p in usable]
    if spec.store_raw:
        now = utcnow()
        upsert(
            session,
            DataPoint,
            [
                {
                    "data_type": spec.key,
                    "start_ts": start,
                    "end_ts": end,
                    "source_id": source_id(p),
                    "value_json": p,
                    "ingested_at": now,
                }
                for p, (start, end) in zip(usable, bounds, strict=True)
            ],
            index_elements=["data_type", "start_ts", "end_ts", "source_id"],
        )

    handler = _HANDLERS.get(spec.key)
    if handler is not None:
        handler(session, spec, usable)
    return StoreResult(len(usable), min(start for start, _ in bounds))


RENORMALIZE_BATCH = 2000


def renormalize(session: Session, spec: DataTypeSpec) -> int:
    """Re-run the typed mapping for `spec` over its stored raw JSON. Caller commits."""
    handler = _HANDLERS.get(spec.key)
    if handler is None or not spec.store_raw:
        return 0
    total = 0
    last_id = 0
    while True:
        rows = session.execute(
            select(DataPoint.id, DataPoint.value_json)
            .where(DataPoint.data_type == spec.key, DataPoint.id > last_id)
            .order_by(DataPoint.id)
            .limit(RENORMALIZE_BATCH)
        ).all()
        if not rows:
            return total
        points = [value for _, value in rows if isinstance(value.get(spec.field), dict)]
        if points:
            handler(session, spec, points)
        total += len(points)
        last_id = rows[-1][0]


def source_id(point: Point) -> str:
    # Reconciled points carry `dataPointName`; listed points carry `name`.
    return str(point.get("dataPointName") or point.get("name") or "")


def point_bounds(spec: DataTypeSpec, point: Point) -> tuple[dt.datetime, dt.datetime]:
    """[start, end) of a data point, in UTC."""
    if spec.kind is RecordKind.ROLLUP:
        start = start_of_day_utc(parse_date(point["civilStartTime"]["date"]))
        end = start_of_day_utc(parse_date(point["civilEndTime"]["date"]))
        return start, end
    body = point[spec.field]
    if spec.kind is RecordKind.SAMPLE:
        ts = parse_ts(body["sampleTime"]["physicalTime"])
        return ts, ts
    if spec.kind is RecordKind.DAILY:
        start = start_of_day_utc(parse_date(body["date"]))
        return start, start + dt.timedelta(days=1)
    interval = body["interval"]
    return parse_ts(interval["startTime"]), parse_ts(interval["endTime"])


# --- Samples -----------------------------------------------------------------------------


def _sample_ts(body: Point) -> dt.datetime:
    return parse_ts(body["sampleTime"]["physicalTime"])


def _heart_rate(session: Session, spec: DataTypeSpec, points: list[Point]) -> None:
    rows = []
    for p in points:
        body = p[spec.field]
        rows.append(
            {
                "ts": _sample_ts(body),
                "bpm": int(body["beatsPerMinute"]),
                "motion_context": body.get("metadata", {}).get("motionContext"),
            }
        )
    upsert(session, HrSample, rows, index_elements=["ts"])


def _hrv(session: Session, spec: DataTypeSpec, points: list[Point]) -> None:
    rows = []
    for p in points:
        body = p[spec.field]
        rmssd = body.get("rootMeanSquareOfSuccessiveDifferencesMilliseconds")
        if rmssd is not None:
            rows.append({"ts": _sample_ts(body), "rmssd_ms": float(rmssd)})
    upsert(session, HrvSample, rows, index_elements=["ts"])


def _spo2(session: Session, spec: DataTypeSpec, points: list[Point]) -> None:
    rows = []
    for p in points:
        body = p[spec.field]
        if body.get("percentage") is not None:
            rows.append({"ts": _sample_ts(body), "spo2_pct": float(body["percentage"])})
    upsert(session, Spo2Sample, rows, index_elements=["ts"])


# --- Intervals -> per-minute activity ----------------------------------------------------


def _minute_values(column: str, value_of: Callable[[Point], Any]) -> Handler:
    """Assign each interval's value to the minute it starts in."""

    def handler(session: Session, spec: DataTypeSpec, points: list[Point]) -> None:
        rows: dict[dt.datetime, Any] = {}
        for p in points:
            body = p[spec.field]
            value = value_of(body)
            if value is None:
                continue
            minute = floor_minute(parse_ts(body["interval"]["startTime"]))
            rows[minute] = value
        upsert(
            session,
            ActivityMinute,
            [{"ts": ts, column: value} for ts, value in rows.items()],
            index_elements=["ts"],
        )

    return handler


def _activity_level(session: Session, spec: DataTypeSpec, points: list[Point]) -> None:
    """An activity-level interval can span many minutes: tag every minute it covers."""
    rows: dict[dt.datetime, str] = {}
    for p in points:
        body = p[spec.field]
        level = body.get("activityLevelType")
        if not level:
            continue
        minute = floor_minute(parse_ts(body["interval"]["startTime"]))
        end = parse_ts(body["interval"]["endTime"])
        while minute < end:
            rows[minute] = str(level)
            minute += dt.timedelta(minutes=1)
    upsert(
        session,
        ActivityMinute,
        [{"ts": ts, "activity_level": level} for ts, level in rows.items()],
        index_elements=["ts"],
    )


def _optional_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None


# --- Sessions ----------------------------------------------------------------------------


def _local_date(ts: dt.datetime, offset: str | None) -> dt.date:
    return (ts + parse_offset(offset)).date()


def _sleep(session: Session, spec: DataTypeSpec, points: list[Point]) -> None:
    for p in points:
        body = p[spec.field]
        interval = body["interval"]
        start, end = parse_ts(interval["startTime"]), parse_ts(interval["endTime"])
        summary = body.get("summary", {})
        in_period = _optional_float(summary.get("minutesInSleepPeriod"))
        asleep = _optional_float(summary.get("minutesAsleep"))
        metadata = body.get("metadata", {})
        key = source_id(p) or f"sleep:{interval['startTime']}"
        # The night belongs to the local day you wake up on.
        local_date = _local_date(end, interval.get("endUtcOffset"))
        is_main = bool(metadata.get("mainSleep", not metadata.get("nap", False)))

        upsert(
            session,
            SleepSession,
            [
                {
                    "source_key": key,
                    "start_ts": start,
                    "end_ts": end,
                    "local_date": local_date,
                    "duration_min": in_period or (end - start).total_seconds() / 60,
                    "efficiency": 100 * asleep / in_period if asleep and in_period else None,
                    "is_main": is_main,
                }
            ],
            index_elements=["source_key"],
        )
        if is_main:
            # Wake-up offset defines that day's local midnight for scoring (DST, travel).
            offset_min = round(parse_offset(interval.get("endUtcOffset")).total_seconds() / 60)
            upsert(
                session,
                DailyMetric,
                [{"date": local_date, "tz_offset_min": offset_min, "updated_at": utcnow()}],
                index_elements=["date"],
            )
        session_id = session.scalar(select(SleepSession.id).where(SleepSession.source_key == key))
        # Stages get revised as Google reprocesses sleep: replace, don't merge.
        session.execute(delete(SleepStage).where(SleepStage.session_id == session_id))
        session.add_all(
            SleepStage(
                session_id=session_id,
                start_ts=parse_ts(stage["startTime"]),
                end_ts=parse_ts(stage["endTime"]),
                stage=str(stage.get("type", "UNKNOWN")).lower(),
            )
            for stage in body.get("stages", [])
        )


def _exercise(session: Session, spec: DataTypeSpec, points: list[Point]) -> None:
    rows = []
    for p in points:
        body = p[spec.field]
        interval = body["interval"]
        start, end = parse_ts(interval["startTime"]), parse_ts(interval["endTime"])
        duration = parse_duration_minutes(body.get("activeDuration"))
        metrics = body.get("metricsSummary", {})
        distance_mm = _optional_float(metrics.get("distanceMillimeters"))
        rows.append(
            {
                "source_key": source_id(p) or f"exercise:{interval['startTime']}",
                "start_ts": start,
                "end_ts": end,
                "local_date": _local_date(start, interval.get("startUtcOffset")),
                "activity_type": str(body.get("exerciseType", "UNKNOWN")),
                "duration_min": duration or (end - start).total_seconds() / 60,
                "calories": _optional_float(metrics.get("caloriesKcal")),
                "avg_hr": _optional_float(metrics.get("averageHeartRateBeatsPerMinute")),
                # Not provided by the API; Phase 3 can derive it from hr_samples.
                "max_hr": None,
                "distance_m": distance_mm / 1000 if distance_mm is not None else None,
                "zones_json": _exercise_zones(metrics),
            }
        )
    upsert(session, ExerciseSession, rows, index_elements=["source_key"])


def _exercise_zones(metrics: Point) -> dict[str, Any] | None:
    durations = metrics.get("heartRateZoneDurations") or {}
    zones = {
        f"{zone}_min": parse_duration_minutes(durations.get(f"{zone}Time"))
        for zone in ("light", "moderate", "vigorous", "peak")
    }
    azm = _optional_int(metrics.get("activeZoneMinutes"))
    if azm is None and all(v is None for v in zones.values()):
        return None
    return {**zones, "active_zone_minutes": azm}


# --- Daily values -> daily_metrics -------------------------------------------------------

Handler = Callable[[Session, DataTypeSpec, list[Point]], None]


def _daily(values_of: Callable[[Point], dict[str, Any]]) -> Handler:
    """Upsert the columns returned by `values_of` into the point's daily_metrics row.

    Each data type owns its columns, so a missing value overwrites with NULL.
    """

    def handler(session: Session, spec: DataTypeSpec, points: list[Point]) -> None:
        now = utcnow()
        rows: dict[dt.date, dict[str, Any]] = {}
        for p in points:
            values = values_of(p[spec.field])
            if all(v is None for v in values.values()):
                continue
            if spec.kind is RecordKind.ROLLUP:
                day = parse_date(p["civilStartTime"]["date"])
            else:
                day = parse_date(p[spec.field]["date"])
            rows[day] = {"date": day, **values, "updated_at": now}
        upsert(session, DailyMetric, list(rows.values()), index_elements=["date"])

    return handler


def _zone_minutes_sum(body: Point) -> int | None:
    keys = ("sumInFatBurnHeartZone", "sumInCardioHeartZone", "sumInPeakHeartZone")
    values = [int(body[k]) for k in keys if body.get(k) is not None]
    return sum(values) if values else None


def _temperature_delta(body: Point) -> float | None:
    nightly = body.get("nightlyTemperatureCelsius")
    baseline = body.get("baselineTemperatureCelsius")
    if nightly is None or baseline is None:
        return None
    return round(float(nightly) - float(baseline), 3)


_HANDLERS: dict[str, Handler] = {
    "heart-rate": _heart_rate,
    "heart-rate-variability": _hrv,
    "oxygen-saturation": _spo2,
    "steps": _minute_values("steps", lambda b: _optional_int(b.get("count"))),
    "distance": _minute_values(
        "distance_m", lambda b: int(b["millimeters"]) / 1000 if b.get("millimeters") else None
    ),
    "active-energy-burned": _minute_values("calories", lambda b: _optional_float(b.get("kcal"))),
    "activity-level": _activity_level,
    "sleep": _sleep,
    "exercise": _exercise,
    "daily-resting-heart-rate": _daily(
        lambda b: {"resting_hr": _optional_float(b.get("beatsPerMinute"))}
    ),
    "daily-heart-rate-variability": _daily(
        lambda b: {
            "hrv_rmssd_ms": _optional_float(b.get("averageHeartRateVariabilityMilliseconds"))
        }
    ),
    "daily-oxygen-saturation": _daily(
        lambda b: {
            "spo2_avg": _optional_float(b.get("averagePercentage")),
            "spo2_min": _optional_float(b.get("lowerBoundPercentage")),
        }
    ),
    "daily-respiratory-rate": _daily(
        lambda b: {"respiratory_rate": _optional_float(b.get("breathsPerMinute"))}
    ),
    "daily-sleep-temperature-derivations": _daily(
        lambda b: {"skin_temp_delta_c": _temperature_delta(b)}
    ),
    "daily-vo2-max": _daily(lambda b: {"vo2_max": _optional_float(b.get("vo2Max"))}),
    # Rollup value fields follow {field}_{aggregation} (verified live 2026-10-29).
    "steps:daily": _daily(lambda b: {"steps": _optional_int(b.get("countSum"))}),
    "distance:daily": _daily(
        lambda b: {
            "distance_m": int(b["millimetersSum"]) / 1000 if b.get("millimetersSum") else None
        }
    ),
    "total-calories:daily": _daily(lambda b: {"total_calories": _optional_float(b.get("kcalSum"))}),
    "active-energy-burned:daily": _daily(
        lambda b: {"active_calories": _optional_float(b.get("kcalSum"))}
    ),
    "active-zone-minutes:daily": _daily(lambda b: {"active_zone_minutes": _zone_minutes_sum(b)}),
}

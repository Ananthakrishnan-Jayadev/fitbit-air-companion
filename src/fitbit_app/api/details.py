"""Intraday detail for one day: /api/heart, /api/sleep, /api/activity, /api/exercise."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from fitbit_app.analytics.downsample import lttb_indices
from fitbit_app.analytics.sleep import stage_minutes
from fitbit_app.analytics.stress import stress_timeline
from fitbit_app.api.dashboard import data_range
from fitbit_app.api.deps import get_session
from fitbit_app.ingest.timeutil import start_of_day_utc
from fitbit_app.storage.models import DailyMetric, DataPoint, ExerciseSession, Score, SleepSession
from fitbit_app.storage.queries import (
    DayClock,
    load_activity,
    load_hr,
    load_hrv,
    load_spo2,
    main_sleep,
    sleep_intervals,
    sleep_stages,
)

router = APIRouter(tags=["details"])

SessionDep = Annotated[Session, Depends(get_session)]

# [epoch milliseconds, value]: compact and what ECharts' time axis expects.
Series = list[tuple[int, float]]
STRESS_BUCKET = "5min"


class HrZone(BaseModel):
    zone: str
    min_bpm: int | None
    max_bpm: int | None


class HeartResponse(BaseModel):
    date: dt.date
    utc_offset_min: int
    samples: Series
    sample_count: int
    resting_hr: float | None
    hrv_rmssd_ms: float | None
    min_bpm: int | None
    max_bpm: int | None
    zones: list[HrZone]


class Stage(BaseModel):
    start: dt.datetime
    end: dt.datetime
    stage: str


class SleepNightOut(BaseModel):
    start: dt.datetime
    end: dt.datetime
    duration_min: float
    efficiency: float | None
    is_main: bool


class SleepResponse(BaseModel):
    date: dt.date
    utc_offset_min: int
    night: SleepNightOut | None
    stages: list[Stage]
    stage_minutes: dict[str, float]
    score: float | None
    components: dict[str, Any] = Field(default_factory=dict)
    spo2: Series
    hrv: Series
    skin_temp_delta_c: float | None
    respiratory_rate: float | None
    spo2_avg: float | None


class NightSummary(BaseModel):
    date: dt.date
    start: dt.datetime
    end: dt.datetime
    bedtime_local: str
    wake_local: str
    duration_min: float
    asleep_min: float | None
    stage_minutes: dict[str, float]
    score: float | None


class Workout(BaseModel):
    date: dt.date
    start: dt.datetime
    end: dt.datetime
    activity_type: str
    duration_min: float
    calories: float | None
    avg_hr: float | None
    max_hr: float | None
    distance_m: float | None
    zones: dict[str, Any] | None


class HourBucket(BaseModel):
    start: int  # epoch ms
    steps: int
    calories: float


class ActivityResponse(BaseModel):
    date: dt.date
    utc_offset_min: int
    hourly: list[HourBucket]
    level_minutes: dict[str, int]
    stress: Series
    stress_avg: float | None
    totals: dict[str, float | None]
    workouts: list[Workout]


@router.get("/heart", response_model=HeartResponse)
def heart(
    session: SessionDep,
    date: dt.date | None = None,
    points: Annotated[int, Query(ge=100, le=5000)] = 1500,
) -> HeartResponse:
    day = _resolve_day(session, date)
    clock = DayClock.load(session)
    start, end = clock.window(day)
    hr = load_hr(session, start, end)
    daily = session.get(DailyMetric, day)
    samples: Series = []
    if not hr.empty:
        ms = _epoch_ms(hr["ts"])
        bpm = hr["bpm"].to_numpy(dtype=float)
        keep = lttb_indices(ms, bpm, points)
        samples = [(int(ms[i]), float(bpm[i])) for i in keep]
    return HeartResponse(
        date=day,
        utc_offset_min=_offset_min(clock, day),
        samples=samples,
        sample_count=len(hr),
        resting_hr=daily.resting_hr if daily else None,
        hrv_rmssd_ms=daily.hrv_rmssd_ms if daily else None,
        min_bpm=int(hr["bpm"].min()) if not hr.empty else None,
        max_bpm=int(hr["bpm"].max()) if not hr.empty else None,
        zones=_zones(session, day),
    )


@router.get("/sleep", response_model=SleepResponse)
def sleep(session: SessionDep, date: dt.date | None = None) -> SleepResponse:
    day = _resolve_day(session, date)
    clock = DayClock.load(session)
    night = main_sleep(session, day)
    daily = session.get(DailyMetric, day)
    score = session.get(Score, day)
    stages = sleep_stages(session, night.id) if night else pd.DataFrame()
    spo2: Series = []
    hrv: Series = []
    if night is not None:
        spo2_frame = load_spo2(session, night.start_ts, night.end_ts)
        hrv_frame = load_hrv(session, night.start_ts, night.end_ts)
        spo2 = _series(spo2_frame, "spo2_pct", 600)
        hrv = _series(hrv_frame, "rmssd_ms", 600)
    components = (score.components_json or {}).get("sleep") if score else None
    return SleepResponse(
        date=day,
        utc_offset_min=_offset_min(clock, day),
        night=SleepNightOut(
            start=night.start_ts,
            end=night.end_ts,
            duration_min=night.duration_min,
            efficiency=night.efficiency,
            is_main=night.is_main,
        )
        if night
        else None,
        stages=[Stage(start=r.start_ts, end=r.end_ts, stage=r.stage) for r in stages.itertuples()]
        if not stages.empty
        else [],
        stage_minutes=stage_minutes(stages) if not stages.empty else {},
        score=score.sleep_perf if score else None,
        components=components or {},
        spo2=spo2,
        hrv=hrv,
        skin_temp_delta_c=daily.skin_temp_delta_c if daily else None,
        respiratory_rate=daily.respiratory_rate if daily else None,
        spo2_avg=daily.spo2_avg if daily else None,
    )


@router.get("/sleep/range", response_model=list[NightSummary])
def sleep_range(session: SessionDep, start: dt.date, end: dt.date) -> list[NightSummary]:
    if end < start or (end - start).days > 400:
        raise HTTPException(400, "Invalid range (max 400 days)")
    clock = DayClock.load(session)
    nights = session.scalars(
        select(SleepSession)
        .where(SleepSession.local_date >= start, SleepSession.local_date <= end)
        .order_by(SleepSession.local_date)
    ).all()
    score_rows = session.scalars(select(Score).where(Score.date >= start, Score.date <= end))
    scores = {s.date: s for s in score_rows}
    result = []
    for day in sorted({n.local_date for n in nights}):
        night = main_sleep(session, day)
        if night is None:
            continue
        offset = clock.offset(day)
        score = scores.get(day)
        sleep_json = (score.components_json or {}).get("sleep") if score else None
        result.append(
            NightSummary(
                date=day,
                start=night.start_ts,
                end=night.end_ts,
                bedtime_local=(night.start_ts + offset).strftime("%H:%M"),
                wake_local=(night.end_ts + offset).strftime("%H:%M"),
                duration_min=night.duration_min,
                asleep_min=(sleep_json or {}).get("asleep_min"),
                stage_minutes=(sleep_json or {}).get("stage_minutes") or {},
                score=score.sleep_perf if score else None,
            )
        )
    return result


@router.get("/activity", response_model=ActivityResponse)
def activity(session: SessionDep, date: dt.date | None = None) -> ActivityResponse:
    day = _resolve_day(session, date)
    clock = DayClock.load(session)
    start, end = clock.window(day)
    minutes = load_activity(session, start, end)
    daily = session.get(DailyMetric, day)
    score = session.get(Score, day)

    hourly: list[HourBucket] = []
    level_minutes: dict[str, int] = {}
    if not minutes.empty:
        grouped = minutes.set_index("ts")[["steps", "calories"]].astype(float).resample("1h").sum()
        hourly = [
            HourBucket(start=int(ms), steps=int(row.steps), calories=round(float(row.calories), 1))
            for ms, row in zip(_epoch_ms(grouped.index), grouped.itertuples(), strict=True)
        ]
        counts = minutes["activity_level"].dropna().value_counts()
        level_minutes = {str(k): int(v) for k, v in counts.items()}

    stress: Series = []
    resting = daily.resting_hr if daily else None
    if resting is not None:
        hr = load_hr(session, start, end)
        if not hr.empty:
            timeline = stress_timeline(hr, minutes, resting, sleep_intervals(session, start, end))
            buckets = timeline["stress"].resample(STRESS_BUCKET).mean().dropna()
            stress = [
                (int(ms), round(float(v), 1))
                for ms, v in zip(_epoch_ms(buckets.index), buckets.to_numpy(), strict=True)
            ]

    totals: dict[str, float | None] = {}
    if daily is not None:
        totals = {
            "steps": daily.steps,
            "distance_m": daily.distance_m,
            "total_calories": daily.total_calories,
            "active_calories": daily.active_calories,
            "active_zone_minutes": daily.active_zone_minutes,
            "sedentary_min": daily.sedentary_min,
        }
    return ActivityResponse(
        date=day,
        utc_offset_min=_offset_min(clock, day),
        hourly=hourly,
        level_minutes=level_minutes,
        stress=stress,
        stress_avg=score.stress_avg if score else None,
        totals=totals,
        workouts=_workouts(session, day, day),
    )


@router.get("/exercise", response_model=list[Workout])
def exercise(session: SessionDep, start: dt.date, end: dt.date) -> list[Workout]:
    if end < start or (end - start).days > 400:
        raise HTTPException(400, "Invalid range (max 400 days)")
    return _workouts(session, start, end)


# --- Helpers -----------------------------------------------------------------------------


def _resolve_day(session: Session, day: dt.date | None) -> dt.date:
    if day is not None:
        return day
    last = data_range(session)[1]
    if last is None:
        raise HTTPException(404, "No scored days yet. Connect Google and let the first sync run.")
    return last


def _offset_min(clock: DayClock, day: dt.date) -> int:
    return int(clock.offset(day).total_seconds() // 60)


def _epoch_ms(values: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    index = pd.DatetimeIndex(values)
    return (index.asi8 // 1_000_000).astype(np.int64)


def _series(frame: pd.DataFrame, column: str, points: int) -> Series:
    if frame.empty:
        return []
    ms = _epoch_ms(frame["ts"])
    values = frame[column].to_numpy(dtype=float)
    keep = lttb_indices(ms, values, points)
    return [(int(ms[i]), round(float(values[i]), 2)) for i in keep]


def _zones(session: Session, day: dt.date) -> list[HrZone]:
    """Google's personal heart-rate zones for the day (daily-heart-rate-zones, raw JSON)."""
    value = session.scalar(
        select(DataPoint.value_json).where(
            DataPoint.data_type == "daily-heart-rate-zones",
            DataPoint.start_ts == start_of_day_utc(day),
        )
    )
    zones = (value or {}).get("dailyHeartRateZones", {}).get("heartRateZones", [])
    return [
        HrZone(
            zone=str(z.get("heartRateZoneType", "UNKNOWN")),
            min_bpm=int(z["minBeatsPerMinute"]) if z.get("minBeatsPerMinute") else None,
            max_bpm=int(z["maxBeatsPerMinute"]) if z.get("maxBeatsPerMinute") else None,
        )
        for z in zones
    ]


def _workouts(session: Session, start: dt.date, end: dt.date) -> list[Workout]:
    rows = session.scalars(
        select(ExerciseSession)
        .where(ExerciseSession.local_date >= start, ExerciseSession.local_date <= end)
        .order_by(ExerciseSession.start_ts)
    ).all()
    return [
        Workout(
            date=w.local_date,
            start=w.start_ts,
            end=w.end_ts,
            activity_type=w.activity_type,
            duration_min=w.duration_min,
            calories=w.calories,
            avg_hr=w.avg_hr,
            max_hr=w.max_hr,
            distance_m=w.distance_m,
            zones=w.zones_json,
        )
        for w in rows
    ]

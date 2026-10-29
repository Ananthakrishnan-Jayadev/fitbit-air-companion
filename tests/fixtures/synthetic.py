"""Deterministic synthetic Fitbit-like data for tests. Never use real health data in tests.

All timestamp columns are timezone-aware UTC. A night of sleep belongs to the local date
the user wakes up on.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection
from dataclasses import dataclass

import numpy as np
import pandas as pd

STAGES = ("light", "deep", "rem", "awake")


@dataclass(frozen=True)
class SyntheticData:
    hr: pd.DataFrame  # ts, bpm
    hrv: pd.DataFrame  # ts, rmssd_ms
    spo2: pd.DataFrame  # ts, spo2_pct
    activity: pd.DataFrame  # ts (minute), steps, activity_level
    sleep_sessions: pd.DataFrame  # session_id, start_ts, end_ts, local_date, duration_min
    sleep_stages: pd.DataFrame  # session_id, start_ts, end_ts, stage
    workouts: pd.DataFrame  # start_ts, end_ts, local_date
    daily: pd.DataFrame  # date, resting_hr, hrv_rmssd_ms, spo2_avg, skin_temp_delta_c, steps


@dataclass(frozen=True)
class _Day:
    date: dt.date
    rhr: float
    hrv: float
    spo2: float
    temp_delta: float


def generate(
    start: dt.date,
    days: int = 30,
    *,
    seed: int = 0,
    tz: str = "UTC",
    hr_interval_s: int = 60,
    sick_days: Collection[dt.date] = (),
) -> SyntheticData:
    """Generate `days` days of data starting at local date `start`.

    `sick_days` get the classic illness signature: higher resting HR, suppressed HRV and
    elevated skin temperature.
    """
    if days < 1:
        raise ValueError("days must be >= 1")
    rng = np.random.default_rng(seed)

    day_params: dict[dt.date, _Day] = {}
    sessions: list[dict[str, object]] = []
    stages: list[dict[str, object]] = []
    workouts: list[dict[str, object]] = []

    for i in range(days):
        day = start + dt.timedelta(days=i)
        sick = day in sick_days
        params = _Day(
            date=day,
            rhr=58 + rng.normal(0, 1.5) + (6 if sick else 0),
            hrv=55 * float(np.exp(rng.normal(0, 0.12))) * (0.7 if sick else 1.0),
            spo2=float(np.clip(96 + rng.normal(0, 0.6), 90, 99.5)),
            temp_delta=rng.normal(0, 0.15) + (0.8 if sick else 0.0),
        )
        day_params[day] = params

        bedtime = _local(day - dt.timedelta(days=1), 23, tz) + pd.Timedelta(
            minutes=rng.normal(0, 30)
        )
        duration_min = float(np.clip(rng.normal(432, 36), 240, 600))
        wake = bedtime + pd.Timedelta(minutes=duration_min)
        sessions.append(
            {
                "session_id": i,
                "start_ts": bedtime.tz_convert("UTC"),
                "end_ts": wake.tz_convert("UTC"),
                "local_date": day,
                "duration_min": duration_min,
            }
        )
        stages.extend(_sleep_stages(i, bedtime.tz_convert("UTC"), wake.tz_convert("UTC"), rng))

        if rng.random() < 0.5:
            w_start = _local(day, 18, tz) + pd.Timedelta(minutes=rng.normal(0, 20))
            workouts.append(
                {
                    "start_ts": w_start.tz_convert("UTC"),
                    "end_ts": (w_start + pd.Timedelta(minutes=45)).tz_convert("UTC"),
                    "local_date": day,
                }
            )

    sessions_df = pd.DataFrame(sessions)
    workouts_df = pd.DataFrame(workouts, columns=["start_ts", "end_ts", "local_date"])
    timeline_start = sessions_df["start_ts"].min().floor("min")
    timeline_end = _local(start + dt.timedelta(days=days), 0, tz).tz_convert("UTC")

    hr = _heart_rate(
        timeline_start, timeline_end, hr_interval_s, tz, day_params, sessions_df, workouts_df, rng
    )
    activity = _activity(timeline_start, timeline_end, tz, sessions_df, workouts_df, rng)
    hrv, spo2 = _overnight_series(sessions_df, day_params, rng)
    daily = _daily(day_params, activity, tz)

    return SyntheticData(
        hr=hr,
        hrv=hrv,
        spo2=spo2,
        activity=activity,
        sleep_sessions=sessions_df,
        sleep_stages=pd.DataFrame(stages),
        workouts=workouts_df,
        daily=daily,
    )


def _local(day: dt.date, hour: int, tz: str) -> pd.Timestamp:
    return pd.Timestamp(dt.datetime.combine(day, dt.time(hour)), tz=tz)


def _sleep_stages(
    session_id: int, start: pd.Timestamp, end: pd.Timestamp, rng: np.random.Generator
) -> list[dict[str, object]]:
    """90-minute cycles: deep sleep front-loaded, REM growing toward morning."""
    rows: list[dict[str, object]] = []
    t = start
    cycle = 0
    while t < end:
        deep = max(0.05, 0.30 - 0.07 * cycle)
        rem = min(0.35, 0.10 + 0.06 * cycle)
        awake = 3.0 if rng.random() < 0.3 else 0.0
        plan = [
            ("light", 90 * (1 - deep - rem) - awake),
            ("deep", 90 * deep),
            ("rem", 90 * rem),
            ("awake", awake),
        ]
        for stage, minutes in plan:
            if minutes <= 0 or t >= end:
                continue
            seg_end = min(t + pd.Timedelta(minutes=minutes), end)
            rows.append(
                {"session_id": session_id, "start_ts": t, "end_ts": seg_end, "stage": stage}
            )
            t = seg_end
        cycle += 1
    return rows


def _within(grid: pd.DatetimeIndex, intervals: pd.DataFrame) -> np.ndarray:
    mask = np.zeros(len(grid), dtype=bool)
    for start, end in zip(intervals["start_ts"], intervals["end_ts"], strict=True):
        mask |= (grid >= start) & (grid < end)
    return mask


def _per_sample(grid: pd.DatetimeIndex, tz: str, values: dict[dt.date, float]) -> np.ndarray:
    # Samples before the first day (the first night) use the first day's values.
    fallback = next(iter(values.values()))
    local_dates = grid.tz_convert(tz).date
    return np.array([values.get(d, fallback) for d in local_dates])


def _heart_rate(
    start: pd.Timestamp,
    end: pd.Timestamp,
    interval_s: int,
    tz: str,
    day_params: dict[dt.date, _Day],
    sessions: pd.DataFrame,
    workouts: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    grid = pd.date_range(start, end, freq=f"{interval_s}s", inclusive="left")
    rhr = _per_sample(grid, tz, {d: p.rhr for d, p in day_params.items()})
    asleep = _within(grid, sessions)
    working_out = _within(grid, workouts)

    bpm = rhr + 18 + rng.normal(0, 5, len(grid))
    bpm = np.where(asleep, rhr - 2 + rng.normal(0, 2, len(grid)), bpm)
    bpm = np.where(working_out, rhr + 80 + rng.normal(0, 6, len(grid)), bpm)
    return pd.DataFrame({"ts": grid, "bpm": np.clip(np.round(bpm), 40, 200).astype(int)})


def _activity(
    start: pd.Timestamp,
    end: pd.Timestamp,
    tz: str,
    sessions: pd.DataFrame,
    workouts: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    grid = pd.date_range(start, end, freq="min", inclusive="left")
    asleep = _within(grid, sessions)
    working_out = _within(grid, workouts)

    walking = rng.random(len(grid)) < 0.1
    steps = np.where(walking, rng.poisson(100, len(grid)), rng.poisson(6, len(grid)))
    steps = np.where(working_out, rng.poisson(160, len(grid)), steps)
    steps = np.where(asleep, 0, steps)

    level = np.select(
        [working_out, steps >= 100, steps >= 20],
        ["vigorous", "moderate", "light"],
        default="sedentary",
    )
    return pd.DataFrame({"ts": grid, "steps": steps.astype(int), "activity_level": level})


def _overnight_series(
    sessions: pd.DataFrame, day_params: dict[dt.date, _Day], rng: np.random.Generator
) -> tuple[pd.DataFrame, pd.DataFrame]:
    hrv_parts: list[pd.DataFrame] = []
    spo2_parts: list[pd.DataFrame] = []
    for row in sessions.itertuples():
        params = day_params[row.local_date]
        hrv_grid = pd.date_range(row.start_ts, row.end_ts, freq="5min", inclusive="left")
        hrv_values = params.hrv * np.exp(rng.normal(0, 0.15, len(hrv_grid)))
        hrv_parts.append(pd.DataFrame({"ts": hrv_grid, "rmssd_ms": hrv_values}))
        spo2_grid = pd.date_range(row.start_ts, row.end_ts, freq="min", inclusive="left")
        spo2_values = np.clip(params.spo2 + rng.normal(0, 0.8, len(spo2_grid)), 85, 100)
        spo2_parts.append(pd.DataFrame({"ts": spo2_grid, "spo2_pct": spo2_values}))
    return (
        pd.concat(hrv_parts, ignore_index=True),
        pd.concat(spo2_parts, ignore_index=True),
    )


def _daily(day_params: dict[dt.date, _Day], activity: pd.DataFrame, tz: str) -> pd.DataFrame:
    steps_by_date = activity.groupby(activity["ts"].dt.tz_convert(tz).dt.date)["steps"].sum()
    return pd.DataFrame(
        [
            {
                "date": d,
                "resting_hr": round(p.rhr, 1),
                "hrv_rmssd_ms": round(p.hrv, 1),
                "spo2_avg": round(p.spo2, 1),
                "skin_temp_delta_c": round(p.temp_delta, 2),
                "steps": int(steps_by_date.get(d, 0)),
            }
            for d, p in day_params.items()
        ]
    )

"""Sleep performance (0-100) from one night's session, its stages and recent bedtimes.

Components (weights renormalized over whatever is available):
- duration (45%): time asleep vs. sleep need
- efficiency (20%): asleep / time in bed, 75% -> 0, 95% -> 100
- restorative (20%): deep + REM share of sleep, 45% or more -> 100
- consistency (15%): SD of bedtime over recent nights, <=15 min -> 100, >=90 min -> 0
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

DEFAULT_SLEEP_NEED_MIN = 480
WEIGHTS = {"duration": 0.45, "efficiency": 0.20, "restorative": 0.20, "consistency": 0.15}
AWAKE_STAGES = frozenset({"awake"})
RESTORATIVE_STAGES = frozenset({"deep", "rem"})
RESTORATIVE_TARGET = 0.45
# Bedtimes are measured from 18:00 so that 23:30 and 00:30 are 60 min apart, not 23 h.
EVENING_ANCHOR_MIN = 18 * 60


@dataclass(frozen=True)
class SleepNight:
    start: dt.datetime
    end: dt.datetime
    duration_min: float  # time in bed
    efficiency: float | None  # % asleep, from Google's summary when available
    stages: pd.DataFrame  # columns: start_ts, end_ts, stage (lowercase)


@dataclass(frozen=True)
class SleepScore:
    score: float | None
    asleep_min: float
    components: dict[str, float | None] = field(default_factory=dict)
    stage_minutes: dict[str, float] = field(default_factory=dict)


def stage_minutes(stages: pd.DataFrame) -> dict[str, float]:
    if stages.empty:
        return {}
    minutes = (stages["end_ts"] - stages["start_ts"]).dt.total_seconds() / 60
    return {str(k): float(v) for k, v in minutes.groupby(stages["stage"]).sum().items()}


def asleep_minutes(night: SleepNight, minutes: dict[str, float] | None = None) -> float:
    minutes = stage_minutes(night.stages) if minutes is None else minutes
    if minutes:
        return sum(v for stage, v in minutes.items() if stage not in AWAKE_STAGES)
    if night.efficiency is not None:
        return night.duration_min * night.efficiency / 100
    return night.duration_min


def minutes_since_evening(local_time: dt.datetime) -> float:
    """Clock time as minutes after 18:00 (wrapping at 24 h)."""
    minute_of_day = local_time.hour * 60 + local_time.minute + local_time.second / 60
    return (minute_of_day - EVENING_ANCHOR_MIN) % 1440


def sleep_performance(
    night: SleepNight,
    *,
    need_min: float = DEFAULT_SLEEP_NEED_MIN,
    bedtimes: Sequence[float] = (),
) -> SleepScore:
    """`bedtimes`: recent nights' bedtimes (incl. this one) as `minutes_since_evening`."""
    minutes = stage_minutes(night.stages)
    asleep = asleep_minutes(night, minutes)

    components: dict[str, float | None] = {
        "duration": _clip(asleep / need_min) * 100 if need_min > 0 else None,
        "efficiency": None,
        "restorative": None,
        "consistency": None,
    }
    efficiency = night.efficiency
    if efficiency is None and night.duration_min > 0 and minutes:
        efficiency = 100 * asleep / night.duration_min
    if efficiency is not None:
        components["efficiency"] = _clip((efficiency - 75) / 20) * 100
    if asleep > 0 and any(stage in RESTORATIVE_STAGES for stage in minutes):
        restorative = sum(minutes.get(stage, 0.0) for stage in RESTORATIVE_STAGES) / asleep
        components["restorative"] = _clip(restorative / RESTORATIVE_TARGET) * 100
    if len(bedtimes) >= 3:
        sd = float(np.std(bedtimes))
        components["consistency"] = _clip(1 - (sd - 15) / 75) * 100

    return SleepScore(
        score=_weighted(components, WEIGHTS),
        asleep_min=asleep,
        components=components,
        stage_minutes=minutes,
    )


def _clip(x: float) -> float:
    return min(1.0, max(0.0, x))


def _weighted(components: dict[str, float | None], weights: dict[str, float]) -> float | None:
    present = {k: v for k, v in components.items() if v is not None}
    if not present:
        return None
    total = sum(weights[k] for k in present)
    return round(sum(weights[k] * v for k, v in present.items()) / total, 1)

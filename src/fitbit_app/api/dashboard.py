"""GET /api/today, /api/daily, /api/trends: day-level scores and metrics."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fitbit_app.analytics import baselines as baseline_stats
from fitbit_app.api.deps import get_session
from fitbit_app.storage.models import Baseline, DailyMetric, Score
from fitbit_app.storage.queries import DAILY_COLUMNS

router = APIRouter(tags=["dashboard"])

SessionDep = Annotated[Session, Depends(get_session)]

SCORE_FIELDS = ("recovery", "sleep_perf", "strain", "stress_avg", "illness_risk")
TrendMetric = Literal[
    "recovery",
    "sleep_perf",
    "strain",
    "stress_avg",
    "resting_hr",
    "hrv_rmssd_ms",
    "spo2_avg",
    "respiratory_rate",
    "skin_temp_delta_c",
    "sleep_min",
    "steps",
    "active_zone_minutes",
    "total_calories",
    "active_calories",
    "distance_m",
    "sedentary_min",
]
MAX_RANGE_DAYS = 400


class BaselineBand(BaseModel):
    typical: float
    low: float
    high: float


class TodayResponse(BaseModel):
    date: dt.date
    first_date: dt.date | None
    last_date: dt.date | None
    recovery: float | None = None
    sleep_perf: float | None = None
    strain: float | None = None
    strain_target: tuple[float, float] | None = None
    stress_avg: float | None = None
    illness_risk: float | None = None
    flags: list[str] = Field(default_factory=list)
    acwr: float | None = None
    components: dict[str, Any] = Field(default_factory=dict)
    z: dict[str, float | None] = Field(default_factory=dict)
    metrics: dict[str, float | None] = Field(default_factory=dict)
    baselines: dict[str, BaselineBand] = Field(default_factory=dict)


class DayRow(BaseModel):
    date: dt.date
    scores: dict[str, float | None]
    metrics: dict[str, float | None]


class TrendPoint(BaseModel):
    date: dt.date
    value: float | None
    baseline: BaselineBand | None = None


class TrendResponse(BaseModel):
    metric: str
    points: list[TrendPoint]


def data_range(session: Session) -> tuple[dt.date | None, dt.date | None]:
    first = session.scalar(select(func.min(Score.date)))
    last = session.scalar(select(func.max(Score.date)))
    return first, last


def bands_for(session: Session, day: dt.date) -> dict[str, BaselineBand]:
    rows = session.scalars(select(Baseline).where(Baseline.as_of == day)).all()
    return {row.metric: _band(row) for row in rows}


@router.get("/today", response_model=TodayResponse)
def today(session: SessionDep, date: dt.date | None = None) -> TodayResponse:
    first, last = data_range(session)
    day = date or last
    if day is None:
        raise HTTPException(404, "No scored days yet. Connect Google and let the first sync run.")
    score = session.get(Score, day)
    daily = session.get(DailyMetric, day)
    components = dict(score.components_json or {}) if score else {}
    target = None
    if score and score.strain_target_low is not None and score.strain_target_high is not None:
        target = (score.strain_target_low, score.strain_target_high)
    return TodayResponse(
        date=day,
        first_date=first,
        last_date=last,
        recovery=score.recovery if score else None,
        sleep_perf=score.sleep_perf if score else None,
        strain=score.strain if score else None,
        strain_target=target,
        stress_avg=score.stress_avg if score else None,
        illness_risk=score.illness_risk if score else None,
        flags=list(components.pop("flags", []) or []),
        acwr=components.pop("acwr", None),
        z=components.pop("z", {}) or {},
        components=components,
        metrics=_metrics(daily),
        baselines=bands_for(session, day),
    )


@router.get("/daily", response_model=list[DayRow])
def daily(session: SessionDep, start: dt.date, end: dt.date) -> list[DayRow]:
    _check_range(start, end)
    metrics = {
        row.date: row
        for row in session.scalars(
            select(DailyMetric).where(DailyMetric.date >= start, DailyMetric.date <= end)
        )
    }
    scores = {
        row.date: row
        for row in session.scalars(select(Score).where(Score.date >= start, Score.date <= end))
    }
    return [
        DayRow(
            date=day,
            scores={f: getattr(scores[day], f) if day in scores else None for f in SCORE_FIELDS},
            metrics=_metrics(metrics.get(day)),
        )
        for day in sorted(metrics.keys() | scores.keys())
    ]


@router.get("/trends", response_model=TrendResponse)
def trends(
    session: SessionDep,
    metric: TrendMetric,
    days: Annotated[int, Query(ge=7, le=MAX_RANGE_DAYS)] = 90,
    end: dt.date | None = None,
) -> TrendResponse:
    last = end or data_range(session)[1] or dt.date.today()
    start = last - dt.timedelta(days=days - 1)
    if metric in SCORE_FIELDS:
        column = getattr(Score, metric)
        rows = session.execute(
            select(Score.date, column).where(Score.date >= start, Score.date <= last)
        ).all()
    else:
        column = getattr(DailyMetric, metric)
        rows = session.execute(
            select(DailyMetric.date, column).where(
                DailyMetric.date >= start, DailyMetric.date <= last
            )
        ).all()
    bands: dict[dt.date, BaselineBand] = {}
    if metric in baseline_stats.BASELINE_METRICS:
        for row in session.scalars(
            select(Baseline).where(
                Baseline.metric == metric, Baseline.as_of >= start, Baseline.as_of <= last
            )
        ):
            bands[row.as_of] = _band(row)
    return TrendResponse(
        metric=metric,
        points=[
            TrendPoint(date=day, value=value, baseline=bands.get(day))
            for day, value in sorted(rows)
        ],
    )


def _metrics(row: DailyMetric | None) -> dict[str, float | None]:
    if row is None:
        return {}
    return {c: getattr(row, c) for c in DAILY_COLUMNS if c not in ("updated_at", "tz_offset_min")}


def _band(row: Baseline) -> BaselineBand:
    stats = baseline_stats.Baseline(row.metric, row.mean, row.sd, row.n)
    low, high = stats.band()
    return BaselineBand(typical=round(stats.typical, 2), low=round(low, 2), high=round(high, 2))


def _check_range(start: dt.date, end: dt.date) -> None:
    if end < start:
        raise HTTPException(400, "end must not be before start")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(400, f"Range is limited to {MAX_RANGE_DAYS} days")

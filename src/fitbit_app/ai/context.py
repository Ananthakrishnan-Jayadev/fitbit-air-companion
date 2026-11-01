"""Builds the compact, numbers-only context the LLM sees (project.md §8.2). Sync: DB reads.

Raw series never reach the model; only scores, daily values, z-scores and trends do.
"""

from __future__ import annotations

import datetime as dt
import json
from statistics import fmean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fitbit_app.analytics.features import feature_pack, trend_direction
from fitbit_app.journal import effects_for, tags_by_day
from fitbit_app.storage.models import DailyMetric, ExerciseSession, Score
from fitbit_app.storage.queries import DayClock, main_sleep

# Sections dropped (in this order) when the context is over budget.
OPTIONAL_SECTIONS = ("workouts", "known_effects", "recovery_drivers", "trend_7d", "sleep")
# Journal history used to find which tags reliably move next-day recovery.
EFFECT_WINDOW_DAYS = 180
MAX_KNOWN_EFFECTS = 3
MAX_CONTEXT_CHARS = 6000

TREND_SOURCES = {
    "recovery": ("score", "recovery"),
    "hrv": ("daily", "hrv_rmssd_ms"),
    "resting_hr": ("daily", "resting_hr"),
    "sleep_min": ("daily", "sleep_min"),
    "strain": ("score", "strain"),
}
DAY_METRICS = (
    "resting_hr",
    "hrv_rmssd_ms",
    "spo2_avg",
    "respiratory_rate",
    "skin_temp_delta_c",
    "sleep_min",
    "steps",
    "active_zone_minutes",
    "total_calories",
    "weight_kg",
    "body_fat_pct",
)
WEEK_METRICS = {
    "recovery": ("score", "recovery"),
    "sleep_perf": ("score", "sleep_perf"),
    "strain": ("score", "strain"),
    "resting_hr": ("daily", "resting_hr"),
    "hrv_rmssd_ms": ("daily", "hrv_rmssd_ms"),
    "sleep_min": ("daily", "sleep_min"),
    "steps": ("daily", "steps"),
    "weight_kg": ("daily", "weight_kg"),
}


def latest_scored_day(session: Session) -> dt.date | None:
    return session.scalar(select(Score.date).order_by(Score.date.desc()).limit(1))


def day_context(session: Session, day: dt.date) -> dict[str, Any] | None:
    score = session.get(Score, day)
    daily = session.get(DailyMetric, day)
    if score is None and daily is None:
        return None
    components = (score.components_json or {}) if score else {}
    history = _history(session, day - dt.timedelta(days=6), day)

    yesterday = session.get(Score, day - dt.timedelta(days=1))
    scores = {
        "recovery": score.recovery if score else None,
        "sleep_perf": score.sleep_perf if score else None,
        "strain_so_far_today": score.strain if score else None,
        "strain_yesterday": yesterday.strain if yesterday else None,
        "strain_target_low": score.strain_target_low if score else None,
        "strain_target_high": score.strain_target_high if score else None,
        "stress_avg": score.stress_avg if score else None,
        "illness_risk": score.illness_risk if score else None,
    }
    trends = {
        name: trend_direction([_value(history.get(d), source, field) for d in _days(day, 7)])
        for name, (source, field) in TREND_SOURCES.items()
    }
    yesterday_tags = tags_by_day(session, day - dt.timedelta(days=1), day - dt.timedelta(days=1))
    pack = feature_pack(
        day=day,
        scores=scores,
        metrics={m: getattr(daily, m) if daily else None for m in DAY_METRICS},
        z_scores=components.get("z") or {},
        trends=trends,
        flags=components.get("flags") or [],
        sleep=_sleep_summary(session, day, components.get("sleep")),
        journal=next(iter(yesterday_tags.values()), []),
    )
    pack["known_effects"] = _known_effects(session, day)
    drivers = (components.get("recovery") or {}).get("components") or {}
    pack["recovery_drivers"] = {k: round(v) for k, v in drivers.items() if v is not None}
    pack["workouts"] = _workouts(session, day - dt.timedelta(days=1), day)
    return fit_budget(pack)


def week_context(session: Session, end: dt.date) -> dict[str, Any] | None:
    history = _history(session, end - dt.timedelta(days=13), end)
    this_week = _days(end, 7)
    if not any(d in history for d in this_week):
        return None
    previous_week = _days(end - dt.timedelta(days=7), 7)
    return fit_budget(
        {
            "week_ending": end.isoformat(),
            "this_week": _averages(history, this_week),
            "previous_week": _averages(history, previous_week),
            "days": [_day_row(d, history.get(d)) for d in this_week if d in history],
        }
    )


def recent_days(session: Session, end: dt.date, days: int = 7) -> list[dict[str, Any]]:
    history = _history(session, end - dt.timedelta(days=days - 1), end)
    return [_day_row(d, history.get(d)) for d in _days(end, days) if d in history]


def fit_budget(pack: dict[str, Any], max_chars: int = MAX_CONTEXT_CHARS) -> dict[str, Any]:
    """Drop optional sections until the JSON fits; keeps the model's context small."""
    trimmed = dict(pack)
    for section in OPTIONAL_SECTIONS:
        if len(json.dumps(trimmed)) <= max_chars:
            break
        trimmed.pop(section, None)
    if "days" in trimmed:
        while len(json.dumps(trimmed)) > max_chars and len(trimmed["days"]) > 1:
            trimmed["days"] = trimmed["days"][1:]
    return trimmed


# --- Helpers -----------------------------------------------------------------------------

_Row = tuple[Score | None, DailyMetric | None]


def _days(end: dt.date, count: int) -> list[dt.date]:
    """`count` days ending at `end`, oldest first."""
    return [end - dt.timedelta(days=i) for i in range(count - 1, -1, -1)]


def _history(session: Session, start: dt.date, end: dt.date) -> dict[dt.date, _Row]:
    scores = {
        s.date: s
        for s in session.scalars(select(Score).where(Score.date >= start, Score.date <= end))
    }
    dailies = {
        d.date: d
        for d in session.scalars(
            select(DailyMetric).where(DailyMetric.date >= start, DailyMetric.date <= end)
        )
    }
    return {day: (scores.get(day), dailies.get(day)) for day in scores.keys() | dailies.keys()}


def _value(row: _Row | None, source: str, field: str) -> float | None:
    if row is None:
        return None
    obj = row[0] if source == "score" else row[1]
    value = getattr(obj, field) if obj is not None else None
    return float(value) if value is not None else None


def _averages(history: dict[dt.date, _Row], days: list[dt.date]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for name, (source, field) in WEEK_METRICS.items():
        values = [v for d in days if (v := _value(history.get(d), source, field)) is not None]
        result[name] = round(fmean(values), 1) if values else None
    return result


def _day_row(day: dt.date, row: _Row | None) -> dict[str, Any]:
    values = {name: _value(row, s, f) for name, (s, f) in WEEK_METRICS.items()}
    return {
        "date": day.isoformat(),
        **{k: round(v, 1) for k, v in values.items() if v is not None},
    }


def _sleep_summary(
    session: Session, day: dt.date, sleep_json: dict[str, Any] | None
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    night = main_sleep(session, day)
    if night is not None:
        offset = DayClock.load(session).offset(day)
        summary["bedtime_local"] = (night.start_ts + offset).strftime("%H:%M")
        summary["wake_local"] = (night.end_ts + offset).strftime("%H:%M")
        summary["time_in_bed_min"] = round(night.duration_min)
    if sleep_json:
        if sleep_json.get("asleep_min") is not None:
            summary["asleep_min"] = round(sleep_json["asleep_min"])
        for stage, minutes in (sleep_json.get("stage_minutes") or {}).items():
            summary[f"{stage}_min"] = round(minutes)
    return summary


def _known_effects(session: Session, day: dt.date) -> list[dict[str, Any]]:
    """Tags that reliably moved next-day recovery in the user's own history."""
    effects, _ = effects_for(
        session, "recovery", day - dt.timedelta(days=EFFECT_WINDOW_DAYS), day - dt.timedelta(days=1)
    )
    return [
        {"tag": e.tag, "next_day_recovery_change": e.difference, "days_with_tag": e.n_with}
        for e in effects
        if e.confident
    ][:MAX_KNOWN_EFFECTS]


def _workouts(session: Session, start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(ExerciseSession).where(
            ExerciseSession.local_date >= start, ExerciseSession.local_date <= end
        )
    ).all()
    return [
        {
            "date": w.local_date.isoformat(),
            "type": w.activity_type.lower(),
            "duration_min": round(w.duration_min),
            **({"avg_hr": round(w.avg_hr)} if w.avg_hr else {}),
        }
        for w in rows
    ]

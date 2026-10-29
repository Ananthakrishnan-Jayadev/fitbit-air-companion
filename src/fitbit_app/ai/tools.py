"""Read-only tools the coach can call during chat to look up the user's history.

Every tool returns compact JSON (daily values and summaries, never raw intraday series) and
validates its arguments, because the model chooses them.
"""

from __future__ import annotations

import datetime as dt
import json
from statistics import fmean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fitbit_app.ai import context as ctx
from fitbit_app.journal import OUTCOMES, effects_for, tags_by_day
from fitbit_app.storage.models import DailyMetric, Score

MAX_RANGE_DAYS = 366

METRICS: dict[str, tuple[Any, str]] = {
    "recovery": (Score, "recovery"),
    "sleep_perf": (Score, "sleep_perf"),
    "strain": (Score, "strain"),
    "stress_avg": (Score, "stress_avg"),
    "resting_hr": (DailyMetric, "resting_hr"),
    "hrv_rmssd_ms": (DailyMetric, "hrv_rmssd_ms"),
    "spo2_avg": (DailyMetric, "spo2_avg"),
    "respiratory_rate": (DailyMetric, "respiratory_rate"),
    "skin_temp_delta_c": (DailyMetric, "skin_temp_delta_c"),
    "sleep_min": (DailyMetric, "sleep_min"),
    "steps": (DailyMetric, "steps"),
    "active_zone_minutes": (DailyMetric, "active_zone_minutes"),
    "total_calories": (DailyMetric, "total_calories"),
}


def _date_param(description: str) -> dict[str, str]:
    return {"type": "string", "description": f"{description} (YYYY-MM-DD)"}


# Ollama / OpenAI-style function definitions.
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_metric_history",
            "description": "Daily values of one metric between two dates, with mean/min/max.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "enum": sorted(METRICS)},
                    "start_date": _date_param("First day"),
                    "end_date": _date_param("Last day"),
                },
                "required": ["metric", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_day_summary",
            "description": "Scores, metrics, sleep and flags for one day.",
            "parameters": {
                "type": "object",
                "properties": {"date": _date_param("The day")},
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_journal",
            "description": "Tags the user logged per day between two dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": _date_param("First day"),
                    "end_date": _date_param("Last day"),
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tag_effects",
            "description": "How each journal tag changed a next-day outcome, from history.",
            "parameters": {
                "type": "object",
                "properties": {"outcome": {"type": "string", "enum": sorted(OUTCOMES)}},
                "required": ["outcome"],
            },
        },
    },
]


class ToolError(ValueError):
    """Bad arguments from the model; reported back to it as the tool result."""


def run_tool(session: Session, name: str, arguments: dict[str, Any], today: dt.date) -> str:
    """Execute a tool and return its JSON result (errors are returned, not raised)."""
    try:
        if name == "get_metric_history":
            result = _metric_history(session, arguments)
        elif name == "get_day_summary":
            day = _parse_date(arguments.get("date"))
            result = ctx.day_context(session, day) or {"note": f"No data for {day}"}
        elif name == "get_journal":
            start, end = _range(arguments)
            journal = tags_by_day(session, start, end)
            result = {d.isoformat(): t for d, t in sorted(journal.items())}
        elif name == "get_tag_effects":
            outcome = str(arguments.get("outcome", "recovery"))
            if outcome not in OUTCOMES:
                raise ToolError(f"Unknown outcome {outcome!r}")
            effects, logged = effects_for(session, outcome, today - dt.timedelta(days=180), today)
            result = {
                "logged_days": logged,
                "effects": [{**e.__dict__, "confident": e.confident} for e in effects],
            }
        else:
            raise ToolError(f"Unknown tool {name!r}")
    except ToolError as exc:
        result = {"error": str(exc)}
    return json.dumps(result, default=str)


def _metric_history(session: Session, arguments: dict[str, Any]) -> dict[str, Any]:
    metric = str(arguments.get("metric", ""))
    if metric not in METRICS:
        raise ToolError(f"Unknown metric {metric!r}; use one of {sorted(METRICS)}")
    start, end = _range(arguments)
    table, column = METRICS[metric]
    rows = session.execute(
        select(table.date, getattr(table, column))
        .where(table.date >= start, table.date <= end)
        .order_by(table.date)
    ).all()
    values = [(d, float(v)) for d, v in rows if v is not None]
    numbers = [v for _, v in values]
    return {
        "metric": metric,
        "days": [{"date": d.isoformat(), "value": round(v, 2)} for d, v in values],
        "mean": round(fmean(numbers), 2) if numbers else None,
        "min": round(min(numbers), 2) if numbers else None,
        "max": round(max(numbers), 2) if numbers else None,
    }


def _parse_date(value: Any) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ToolError(f"Invalid date {value!r}; use YYYY-MM-DD") from exc


def _range(arguments: dict[str, Any]) -> tuple[dt.date, dt.date]:
    start = _parse_date(arguments.get("start_date"))
    end = _parse_date(arguments.get("end_date"))
    if end < start:
        start, end = end, start
    if (end - start).days > MAX_RANGE_DAYS:
        start = end - dt.timedelta(days=MAX_RANGE_DAYS)
    return start, end

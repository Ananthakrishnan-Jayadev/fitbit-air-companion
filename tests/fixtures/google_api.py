"""Fake Google Health API payloads, shaped like the documented JSON. Synthetic values only.

Reference: https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from fitbit_app.ingest.scopes import READ_SCOPES

EDT = "-14400s"  # UTC-4

Point = dict[str, Any]


def civil(day: dt.date) -> dict[str, int]:
    return {"year": day.year, "month": day.month, "day": day.day}


def _name(data_type: str, suffix: str) -> str:
    return f"users/me/dataTypes/{data_type}/dataPoints/{suffix}"


def _interval(start: str, end: str, offset: str = EDT) -> dict[str, str]:
    return {"startTime": start, "startUtcOffset": offset, "endTime": end, "endUtcOffset": offset}


def heart_rate(ts: str, bpm: int, motion: str = "SEDENTARY") -> Point:
    return {
        "dataPointName": _name("heart-rate", f"hr-{ts}"),
        "heartRate": {
            "sampleTime": {"physicalTime": ts, "utcOffset": EDT},
            "beatsPerMinute": str(bpm),
            "metadata": {"motionContext": motion, "sensorLocation": "WRIST"},
        },
    }


def hrv(ts: str, rmssd: float) -> Point:
    return {
        "dataPointName": _name("heart-rate-variability", f"hrv-{ts}"),
        "heartRateVariability": {
            "sampleTime": {"physicalTime": ts, "utcOffset": EDT},
            "rootMeanSquareOfSuccessiveDifferencesMilliseconds": rmssd,
        },
    }


def spo2(ts: str, pct: float) -> Point:
    return {
        "dataPointName": _name("oxygen-saturation", f"spo2-{ts}"),
        "oxygenSaturation": {
            "sampleTime": {"physicalTime": ts, "utcOffset": EDT},
            "percentage": pct,
        },
    }


def weight(ts: str, kg: float, offset: str = EDT) -> Point:
    return {
        "dataPointName": _name("weight", f"w-{ts}"),
        "weight": {
            "sampleTime": {"physicalTime": ts, "utcOffset": offset},
            "weightGrams": kg * 1000,
        },
    }


def body_fat(ts: str, pct: float, offset: str = EDT) -> Point:
    return {
        "dataPointName": _name("body-fat", f"bf-{ts}"),
        "bodyFat": {"sampleTime": {"physicalTime": ts, "utcOffset": offset}, "percentage": pct},
    }


def steps(start: str, end: str, count: int) -> Point:
    return {
        "dataPointName": _name("steps", f"steps-{start}"),
        "steps": {"interval": _interval(start, end), "count": str(count)},
    }


def distance(start: str, end: str, millimeters: int) -> Point:
    return {
        "dataPointName": _name("distance", f"dist-{start}"),
        "distance": {"interval": _interval(start, end), "millimeters": str(millimeters)},
    }


def activity_level(start: str, end: str, level: str) -> Point:
    return {
        "dataPointName": _name("activity-level", f"al-{start}"),
        "activityLevel": {"interval": _interval(start, end), "activityLevelType": level},
    }


def sleep(
    start: str,
    end: str,
    stages: list[tuple[str, str, str]],
    *,
    name: str = "sleep-1",
    offset: str = EDT,
    minutes_in_period: int | None = None,
    minutes_asleep: int | None = None,
    main: bool = True,
) -> Point:
    summary: dict[str, str] = {}
    if minutes_in_period is not None:
        summary["minutesInSleepPeriod"] = str(minutes_in_period)
    if minutes_asleep is not None:
        summary["minutesAsleep"] = str(minutes_asleep)
    return {
        "dataPointName": _name("sleep", name),
        "sleep": {
            "interval": _interval(start, end, offset),
            "type": "STAGES",
            "stages": [
                {
                    "startTime": s,
                    "startUtcOffset": offset,
                    "endTime": e,
                    "endUtcOffset": offset,
                    "type": t,
                }
                for s, e, t in stages
            ],
            "metadata": {"mainSleep": main, "nap": not main},
            "summary": summary,
        },
    }


def exercise(
    start: str,
    end: str,
    kind: str,
    active_duration: str | None = None,
    metrics: dict[str, Any] | None = None,
) -> Point:
    body: dict[str, Any] = {"interval": _interval(start, end), "exerciseType": kind}
    if active_duration is not None:
        body["activeDuration"] = active_duration
    if metrics is not None:
        body["metricsSummary"] = metrics
    return {"dataPointName": _name("exercise", f"ex-{start}"), "exercise": body}


def daily(field: str, day: dt.date, **values: Any) -> Point:
    data_type = "".join(f"-{c.lower()}" if c.isupper() else c for c in field)
    return {
        "dataPointName": _name(data_type, f"{data_type}-{day.isoformat()}"),
        field: {"date": civil(day), **values},
    }


def rollup(day: dt.date, field: str, **values: Any) -> Point:
    """A DailyRollupDataPoint, e.g. rollup(day, "totalCalories", kcalSum=2100.5)."""
    return {
        "civilStartTime": {"date": civil(day), "time": {}},
        "civilEndTime": {"date": civil(day + dt.timedelta(days=1)), "time": {}},
        field: values,
    }


def rollup_steps(day: dt.date, count: int) -> Point:
    return rollup(day, "steps", countSum=str(count))


def page(points: list[Point], next_token: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"dataPoints": points}
    if next_token:
        body["nextPageToken"] = next_token
    return body


def rollup_page(points: list[Point], next_token: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"rollupDataPoints": points}
    if next_token:
        body["nextPageToken"] = next_token
    return body


def token_response(
    access: str = "access-1",
    refresh: str | None = "refresh-1",
    expires_in: int = 3600,
    scope: str = " ".join(READ_SCOPES),
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "access_token": access,
        "expires_in": expires_in,
        "scope": scope,
        "token_type": "Bearer",
    }
    if refresh:
        body["refresh_token"] = refresh
    return body


def api_error(code: int, status: str, message: str, reason: str | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "status": status, "message": message}
    if reason:
        error["details"] = [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": reason}]
    return {"error": error}

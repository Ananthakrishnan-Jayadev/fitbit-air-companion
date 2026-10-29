"""OAuth scopes. Source: https://developers.google.com/health/scopes (verified 2026-10-29).

Read-only scopes only: this app never writes to Google Health.
"""

from __future__ import annotations

_PREFIX = "https://www.googleapis.com/auth/googlehealth."

ACTIVITY_AND_FITNESS = _PREFIX + "activity_and_fitness.readonly"
HEALTH_METRICS = _PREFIX + "health_metrics_and_measurements.readonly"
SLEEP = _PREFIX + "sleep.readonly"
IRN = _PREFIX + "irn.readonly"

READ_SCOPES: tuple[str, ...] = (ACTIVITY_AND_FITNESS, HEALTH_METRICS, SLEEP, IRN)


def missing_scopes(granted: str) -> list[str]:
    """Scopes we asked for but the user did not grant (consent is per-scope)."""
    granted_set = set(granted.split())
    return [scope for scope in READ_SCOPES if scope not in granted_set]

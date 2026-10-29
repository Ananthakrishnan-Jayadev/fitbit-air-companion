"""Google Health API and Google OAuth endpoints.

Sources (verified 2026-10-29):
- https://developers.google.com/health/reference/rest  (base URL, resource paths)
- https://developers.google.com/health/setup           (auth + token endpoints)
- https://developers.google.com/identity/protocols/oauth2/web-server#tokenrevoke (revoke)
"""

from __future__ import annotations

API_BASE_URL = "https://health.googleapis.com"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"

# "me" is the authenticated user.
USER = "users/me"
IDENTITY_PATH = f"/v4/{USER}/identity"


def data_points_path(version: str, data_type: str) -> str:
    """GET  /{version}/users/me/dataTypes/{data_type}/dataPoints  (list)."""
    return f"/{version}/{USER}/dataTypes/{data_type}/dataPoints"


def reconcile_path(version: str, data_type: str) -> str:
    """GET  .../dataPoints:reconcile. Merges overlapping sources into one stream."""
    return f"{data_points_path(version, data_type)}:reconcile"


def daily_rollup_path(version: str, data_type: str) -> str:
    """POST .../dataPoints:dailyRollUp. Per-civil-day aggregates."""
    return f"{data_points_path(version, data_type)}:dailyRollUp"


def data_source_family(family: str) -> str:
    """`dataSourceFamily` parameter value, e.g. users/me/dataSourceFamilies/google-wearables."""
    return f"{USER}/dataSourceFamilies/{family}"

"""Async Google Health API client: auth, rate limiting, retries and pagination.

Rate limits (https://developers.google.com/health/rate-limits): 300 requests/minute per
user; unverified apps 2.5 QPS per user. Over-limit requests get HTTP 429.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

import httpx

from fitbit_app.errors import GoogleApiError, ReauthRequiredError
from fitbit_app.ingest.endpoints import (
    IDENTITY_PATH,
    daily_rollup_path,
    data_points_path,
    data_source_family,
    reconcile_path,
)
from fitbit_app.ingest.registry import DataTypeSpec, Method
from fitbit_app.ingest.timeutil import to_civil_date

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_BACKOFF_S = 60.0
ROLLUP_PAGE_SIZE = 14  # max for total-calories etc.; fine for all rollup types

Sleep = Callable[[float], Awaitable[None]]


class AccessTokenProvider(Protocol):
    async def access_token(self, *, force_refresh: bool = False) -> str: ...


class StaticToken:
    """A fixed access token, e.g. right after the OAuth code exchange."""

    def __init__(self, token: str) -> None:
        self._token = token

    async def access_token(self, *, force_refresh: bool = False) -> str:
        return self._token


class RateLimiter:
    """Spaces requests at least 1/rate seconds apart."""

    def __init__(
        self,
        rate_per_s: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._interval = 1.0 / rate_per_s
        self._clock = clock
        self._sleep = sleep
        self._next_at = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            delay = self._next_at - self._clock()
            if delay > 0:
                await self._sleep(delay)
            self._next_at = max(self._clock(), self._next_at) + self._interval


class GoogleHealthClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        tokens: AccessTokenProvider,
        *,
        requests_per_s: float = 2.0,
        max_retries: int = 5,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._http = http
        self._tokens = tokens
        self._limiter = RateLimiter(requests_per_s, sleep=sleep)
        self._max_retries = max_retries
        self._sleep = sleep

    async def get_identity(self) -> dict[str, Any]:
        return await self._request("GET", IDENTITY_PATH)

    async def iter_pages(self, spec: DataTypeSpec, filter_: str) -> AsyncIterator[list[dict]]:
        """Yield pages of data points for list/reconcile types (newest first)."""
        if spec.method is Method.RECONCILE:
            path = reconcile_path(spec.version, spec.name)
        elif spec.method is Method.LIST:
            path = data_points_path(spec.version, spec.name)
        else:
            raise ValueError(f"{spec.key} must be fetched with daily_rollup_pages")

        params: dict[str, Any] = {"filter": filter_, "pageSize": spec.page_size}
        params["dataSourceFamily"] = data_source_family(spec.family)
        while True:
            body = await self._request("GET", path, params=params)
            yield body.get("dataPoints", [])
            token = body.get("nextPageToken")
            if not token:
                return
            params = {**params, "pageToken": token}

    async def daily_rollup_pages(
        self, spec: DataTypeSpec, first_day: dt.date, end_day: dt.date
    ) -> AsyncIterator[list[dict]]:
        """Yield pages of per-day rollups for civil days [first_day, end_day)."""
        path = daily_rollup_path(spec.version, spec.name)
        payload: dict[str, Any] = {
            "range": {
                "start": {"date": to_civil_date(first_day)},
                "end": {"date": to_civil_date(end_day)},
            },
            "windowSizeDays": 1,
            "pageSize": ROLLUP_PAGE_SIZE,
            "dataSourceFamily": data_source_family(spec.family),
        }
        while True:
            body = await self._request("POST", path, json=payload)
            yield body.get("rollupDataPoints", [])
            token = body.get("nextPageToken")
            if not token:
                return
            payload = {**payload, "pageToken": token}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        refreshed = False
        attempt = 0
        while True:
            await self._limiter.wait()
            token = await self._tokens.access_token(force_refresh=refreshed)
            try:
                response = await self._http.request(
                    method,
                    path,
                    params=params,
                    json=json,
                    headers={"Authorization": f"Bearer {token}"},
                )
            except httpx.TransportError as exc:
                if attempt >= self._max_retries:
                    raise
                attempt += 1
                await self._backoff(attempt, None, type(exc).__name__)
                continue

            if response.status_code == 401:
                if refreshed:
                    raise ReauthRequiredError("Google rejected a freshly refreshed token")
                refreshed = True
                continue
            if response.status_code in RETRYABLE_STATUS and attempt < self._max_retries:
                attempt += 1
                await self._backoff(attempt, response, f"HTTP {response.status_code}")
                continue
            if response.status_code >= 400:
                raise _api_error(response)
            return response.json()

    async def _backoff(self, attempt: int, response: httpx.Response | None, why: str) -> None:
        delay = _retry_after(response)
        if delay is None:
            delay = min(MAX_BACKOFF_S, 2.0**attempt) + random.uniform(0, 1)
        logger.warning("Google Health API %s; retry %d in %.1fs", why, attempt, delay)
        await self._sleep(delay)


def _retry_after(response: httpx.Response | None) -> float | None:
    if response is None:
        return None
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return min(MAX_BACKOFF_S, float(value))
    except ValueError:
        return None


def _api_error(response: httpx.Response) -> GoogleApiError:
    """Extract status/reason from a google.rpc.Status error body (never the payload data)."""
    reason = f"HTTP_{response.status_code}"
    message = ""
    try:
        error = response.json().get("error", {})
    except ValueError:
        error = {}
    if isinstance(error, dict):
        message = str(error.get("message", ""))[:300]
        reason = str(error.get("status") or reason)
        for detail in error.get("details", []) or []:
            if isinstance(detail, dict) and detail.get("reason"):
                reason = str(detail["reason"])
                break
    if "ACCOUNT_NOT_LINKED" in message:
        reason = "ACCOUNT_NOT_LINKED"
    return GoogleApiError(response.status_code, reason, message)

"""SyncEngine: pulls data types window by window and stores them.

Per data type, `sync_state` tracks the synced range [synced_from, cursor). Each run:
1. incremental: [cursor - overlap, now), split into chunks, newest first;
2. backfill: from synced_from (or now) back to the target start, newest first.
State is saved after every window, so an interrupted run resumes where it stopped.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Literal

import httpx
from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.errors import GoogleApiError, ReauthRequiredError
from fitbit_app.ingest.client import GoogleHealthClient
from fitbit_app.ingest.registry import DataTypeSpec, RecordKind, build_filter
from fitbit_app.storage.models import SyncState
from fitbit_app.storage.normalize import store_points
from fitbit_app.storage.types import utcnow

logger = logging.getLogger(__name__)

# Phones sync late and Google revises sleep/daily values, so re-read a little history.
_OVERLAP = {
    RecordKind.SAMPLE: dt.timedelta(hours=2),
    RecordKind.INTERVAL: dt.timedelta(hours=2),
    RecordKind.SESSION: dt.timedelta(days=3),
    RecordKind.DAILY: dt.timedelta(days=3),
    RecordKind.ROLLUP: dt.timedelta(days=3),
}


@dataclass(frozen=True)
class Window:
    start: dt.datetime
    end: dt.datetime
    kind: Literal["incremental", "backfill"]


@dataclass(frozen=True)
class Cursor:
    cursor: dt.datetime | None
    synced_from: dt.datetime | None


@dataclass
class SyncReport:
    started_at: dt.datetime
    finished_at: dt.datetime | None = None
    ok: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    points: dict[str, int] = field(default_factory=dict)


def plan_windows(
    spec: DataTypeSpec, state: Cursor, now: dt.datetime, target_start: dt.datetime
) -> list[Window]:
    chunk = dt.timedelta(days=spec.chunk_days)
    windows: list[Window] = []

    if state.cursor is not None:
        windows += _split(state.cursor - _OVERLAP[spec.kind], now, chunk, "incremental")
        backfill_end = state.synced_from or state.cursor
    else:
        backfill_end = now

    windows += _split(target_start, backfill_end, chunk, "backfill")
    return windows


def _split(
    start: dt.datetime,
    end: dt.datetime,
    chunk: dt.timedelta,
    kind: Literal["incremental", "backfill"],
) -> list[Window]:
    """[start, end) in chunks, newest first."""
    windows = []
    while end > start:
        lower = max(end - chunk, start)
        windows.append(Window(lower, end, kind))
        end = lower
    return windows


class SyncEngine:
    def __init__(
        self,
        client: GoogleHealthClient,
        session_factory: sessionmaker[Session],
        *,
        backfill_days: int,
        clock: Callable[[], dt.datetime] = utcnow,
    ) -> None:
        self._client = client
        self._session_factory = session_factory
        self._backfill = dt.timedelta(days=backfill_days)
        self._clock = clock

    async def run(self, specs: list[DataTypeSpec], since: dt.date | None = None) -> SyncReport:
        now = self._clock()
        target = (
            dt.datetime.combine(since, dt.time(), tzinfo=dt.UTC) if since else now - self._backfill
        )
        report = SyncReport(started_at=now)
        for spec in specs:
            try:
                report.points[spec.key] = await self._sync_spec(spec, now, target)
                report.ok.append(spec.key)
            except ReauthRequiredError:
                raise
            except (GoogleApiError, httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
                # One bad type must not stop the others. Messages never contain health data.
                message = _describe(exc)
                logger.error("Sync of %s failed: %s", spec.key, message)
                report.failed[spec.key] = message
                await asyncio.to_thread(self._record_error, spec.key, message)
        report.finished_at = self._clock()
        logger.info(
            "Sync finished: %d ok, %d failed, %d points",
            len(report.ok),
            len(report.failed),
            sum(report.points.values()),
        )
        return report

    async def _sync_spec(self, spec: DataTypeSpec, now: dt.datetime, target: dt.datetime) -> int:
        state = await asyncio.to_thread(self._load_cursor, spec.key)
        windows = plan_windows(spec, state, now, target)
        total = 0
        for window in windows:
            async for page in self._pages(spec, window):
                total += await asyncio.to_thread(self._store, spec, page)
            await asyncio.to_thread(self._advance, spec.key, window)
        await asyncio.to_thread(self._record_success, spec.key)
        logger.info("Synced %s: %d windows, %d points", spec.key, len(windows), total)
        return total

    def _pages(self, spec: DataTypeSpec, window: Window) -> AsyncIterator[list[dict]]:
        if spec.kind is RecordKind.ROLLUP:
            # Civil days [start day, end day + 1) so today's partial day is included.
            return self._client.daily_rollup_pages(
                spec, window.start.date(), window.end.date() + dt.timedelta(days=1)
            )
        return self._client.iter_pages(spec, build_filter(spec, window.start, window.end))

    # --- DB helpers (run in a worker thread) ---

    def _store(self, spec: DataTypeSpec, page: list[dict]) -> int:
        with self._session_factory() as session:
            result = store_points(session, spec, page)
            if result.earliest is not None:
                state = self._state(session, spec.key)
                if state.earliest_seen_at is None or result.earliest < state.earliest_seen_at:
                    state.earliest_seen_at = result.earliest
            session.commit()
            return result.count

    def _load_cursor(self, key: str) -> Cursor:
        with self._session_factory() as session:
            state = session.get(SyncState, key)
            if state is None:
                return Cursor(None, None)
            return Cursor(state.cursor, state.synced_from)

    def _advance(self, key: str, window: Window) -> None:
        with self._session_factory() as session:
            state = self._state(session, key)
            state.last_attempt_at = self._clock()
            if state.cursor is None or window.end > state.cursor:
                state.cursor = window.end
            if state.synced_from is None or window.start < state.synced_from:
                state.synced_from = window.start
            session.commit()

    def _record_success(self, key: str) -> None:
        with self._session_factory() as session:
            state = self._state(session, key)
            state.last_success_at = self._clock()
            state.last_error = None
            session.commit()

    def _record_error(self, key: str, message: str) -> None:
        with self._session_factory() as session:
            state = self._state(session, key)
            state.last_attempt_at = state.last_error_at = self._clock()
            state.last_error = message
            session.commit()

    @staticmethod
    def _state(session: Session, key: str) -> SyncState:
        state = session.get(SyncState, key)
        if state is None:
            state = SyncState(data_type=key)
            session.add(state)
        return state


def _describe(exc: Exception) -> str:
    if isinstance(exc, GoogleApiError):
        return str(exc)
    if isinstance(exc, KeyError | ValueError | TypeError):
        return f"Unexpected response shape ({type(exc).__name__}: {exc})"[:300]
    return f"{type(exc).__name__}"

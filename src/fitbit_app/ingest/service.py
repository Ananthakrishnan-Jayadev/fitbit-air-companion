"""SyncService: one shared entry point for the API, scheduler and CLI to run a sync."""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging
from collections.abc import Awaitable, Callable, Iterable

import httpx
from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.config import Settings
from fitbit_app.errors import FitbitAppError, NotConnectedError, ReauthRequiredError
from fitbit_app.ingest.client import GoogleHealthClient
from fitbit_app.ingest.endpoints import API_BASE_URL
from fitbit_app.ingest.oauth import TokenManager, TokenStore
from fitbit_app.ingest.registry import RecordKind, select_specs
from fitbit_app.ingest.sync import SyncEngine, SyncReport

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = httpx.Timeout(30.0)

AfterSync = Callable[[SyncReport], Awaitable[object]]


class SyncService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        after_sync: AfterSync | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._after_sync = after_sync
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[SyncReport | None] | None = None
        self.last_report: SyncReport | None = None
        self.last_error: str | None = None

    @property
    def token_store(self) -> TokenStore:
        return TokenStore(self._session_factory, self._settings.fitbit_secret_key)

    @property
    def running(self) -> bool:
        return self._lock.locked()

    async def run(
        self,
        *,
        keys: Iterable[str] | None = None,
        kinds: Iterable[RecordKind] | None = None,
        since: dt.date | None = None,
    ) -> SyncReport:
        """Run a sync, waiting for any sync already in progress."""
        specs = select_specs(include_beta=self._settings.enable_beta_types, keys=keys, kinds=kinds)
        async with self._lock:
            store = self.token_store
            async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=HTTP_TIMEOUT) as http:
                client = GoogleHealthClient(
                    http,
                    TokenManager(store, http, self._settings),
                    requests_per_s=self._settings.sync_requests_per_s,
                )
                engine = SyncEngine(
                    client, self._session_factory, backfill_days=self._settings.backfill_days
                )
                try:
                    report = await engine.run(specs, since=since)
                except ReauthRequiredError:
                    await asyncio.to_thread(store.mark_needs_reauth)
                    raise
            self.last_report = report
            self.last_error = None
            if self._after_sync is not None and report.ok:
                try:
                    await self._after_sync(report)
                except Exception:
                    # Scoring problems must never break syncing.
                    logger.exception("Post-sync processing failed")
            return report

    async def run_scheduled(self, kinds: Iterable[RecordKind]) -> None:
        """Scheduler entry point: never raises."""
        try:
            await self.run(kinds=kinds)
        except NotConnectedError:
            logger.debug("Scheduled sync skipped: Google not connected")
        except FitbitAppError as exc:
            self.last_error = str(exc)
            logger.warning("Scheduled sync stopped: %s", exc)

    def start_background(
        self, *, keys: Iterable[str] | None = None, since: dt.date | None = None
    ) -> bool:
        """Start a sync task unless one is running. Returns False if busy."""
        if self.running or (self._task is not None and not self._task.done()):
            return False
        self._task = asyncio.create_task(self._run_logged(keys=keys, since=since))
        return True

    async def _run_logged(
        self, *, keys: Iterable[str] | None, since: dt.date | None
    ) -> SyncReport | None:
        try:
            return await self.run(keys=keys, since=since)
        except FitbitAppError as exc:
            self.last_error = str(exc)
            logger.warning("Background sync stopped: %s", exc)
            return None

    async def shutdown(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

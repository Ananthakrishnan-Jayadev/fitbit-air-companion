"""In-process background jobs (APScheduler, same event loop as the API)."""

from __future__ import annotations

import datetime as dt

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from fitbit_app.config import Settings
from fitbit_app.ingest.registry import FAST_KINDS, SLOW_KINDS
from fitbit_app.ingest.service import SyncService

SLOW_SYNC_INTERVAL_MIN = 60
# First runs shortly after startup instead of one full interval later.
FIRST_FAST_RUN = dt.timedelta(seconds=10)
FIRST_SLOW_RUN = dt.timedelta(seconds=60)


def create_scheduler(settings: Settings, sync_service: SyncService) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    now = dt.datetime.now(dt.UTC)
    common = {"max_instances": 1, "coalesce": True, "misfire_grace_time": 300}
    scheduler.add_job(
        sync_service.run_scheduled,
        "interval",
        minutes=settings.sync_interval_min,
        kwargs={"kinds": FAST_KINDS},
        id="sync-intraday",
        next_run_time=now + FIRST_FAST_RUN,
        **common,
    )
    scheduler.add_job(
        sync_service.run_scheduled,
        "interval",
        minutes=SLOW_SYNC_INTERVAL_MIN,
        kwargs={"kinds": SLOW_KINDS},
        id="sync-daily",
        next_run_time=now + FIRST_SLOW_RUN,
        **common,
    )
    return scheduler

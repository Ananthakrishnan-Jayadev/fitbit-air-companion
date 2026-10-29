import datetime as dt

from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.config import Settings
from fitbit_app.ingest.registry import FAST_KINDS, SLOW_KINDS
from fitbit_app.ingest.service import SyncService
from fitbit_app.scheduler import create_scheduler


def test_jobs(settings: Settings, session_factory: sessionmaker[Session]) -> None:
    scheduler = create_scheduler(settings, SyncService(settings, session_factory))
    jobs = {job.id: job for job in scheduler.get_jobs()}

    assert set(jobs) == {"sync-intraday", "sync-daily"}
    assert jobs["sync-intraday"].trigger.interval == dt.timedelta(minutes=15)
    assert jobs["sync-intraday"].kwargs == {"kinds": FAST_KINDS}
    assert jobs["sync-daily"].trigger.interval == dt.timedelta(hours=1)
    assert jobs["sync-daily"].kwargs == {"kinds": SLOW_KINDS}
    assert all(job.max_instances == 1 and job.coalesce for job in jobs.values())

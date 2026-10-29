import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from fitbit_app.storage.db import create_db_engine, create_session_factory
from fitbit_app.storage.migrate import upgrade_to_head
from fitbit_app.storage.models import HrSample


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_db_engine(tmp_path / "fitbit.db")
    upgrade_to_head(engine)
    with create_session_factory(engine)() as s:
        yield s
    engine.dispose()


def test_aware_datetime_round_trips_as_utc(session: Session) -> None:
    ts = dt.datetime(2026, 10, 1, 8, 30, tzinfo=dt.UTC)
    session.add(HrSample(ts=ts, bpm=60))
    session.commit()
    session.expunge_all()

    loaded = session.get(HrSample, ts)
    assert loaded is not None
    assert loaded.ts == ts
    assert loaded.ts.tzinfo == dt.UTC


def test_non_utc_datetime_is_converted(session: Session) -> None:
    local = dt.datetime(2026, 10, 1, 4, 30, tzinfo=ZoneInfo("America/Toronto"))  # EDT, UTC-4
    session.add(HrSample(ts=local, bpm=61))
    session.commit()
    session.expunge_all()

    loaded = session.get(HrSample, dt.datetime(2026, 10, 1, 8, 30, tzinfo=dt.UTC))
    assert loaded is not None
    assert loaded.bpm == 61


def test_naive_datetime_is_rejected(session: Session) -> None:
    session.add(HrSample(ts=dt.datetime(2026, 10, 1, 8, 30), bpm=60))
    with pytest.raises(StatementError, match="timezone-aware"):
        session.commit()

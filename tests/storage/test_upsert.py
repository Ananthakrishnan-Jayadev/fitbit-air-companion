import datetime as dt
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fitbit_app.storage import upsert as upsert_module
from fitbit_app.storage.db import create_db_engine, create_session_factory
from fitbit_app.storage.migrate import upgrade_to_head
from fitbit_app.storage.models import DataPoint, HrSample
from fitbit_app.storage.upsert import upsert

T0 = dt.datetime(2026, 10, 1, tzinfo=dt.UTC)


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_db_engine(tmp_path / "fitbit.db")
    upgrade_to_head(engine)
    with create_session_factory(engine)() as s:
        yield s
    engine.dispose()


def _hr_rows(n: int, bpm: int) -> list[dict[str, object]]:
    return [{"ts": T0 + dt.timedelta(minutes=i), "bpm": bpm} for i in range(n)]


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_empty_rows_is_noop(session: Session) -> None:
    assert upsert(session, HrSample, [], index_elements=["ts"]) == 0


def test_insert_then_update(session: Session) -> None:
    upsert(session, HrSample, _hr_rows(3, 60), index_elements=["ts"])
    upsert(session, HrSample, _hr_rows(3, 70), index_elements=["ts"])
    session.commit()
    assert _count(session, HrSample) == 3
    assert set(session.scalars(select(HrSample.bpm))) == {70}


def test_insert_or_ignore_keeps_existing(session: Session) -> None:
    upsert(session, HrSample, _hr_rows(2, 60), index_elements=["ts"])
    upsert(session, HrSample, _hr_rows(4, 99), index_elements=["ts"], update_columns=[])
    session.commit()
    bpms = list(session.scalars(select(HrSample.bpm).order_by(HrSample.ts)))
    assert bpms == [60, 60, 99, 99]


def test_composite_natural_key(session: Session) -> None:
    row = {
        "data_type": "heart-rate",
        "start_ts": T0,
        "end_ts": T0 + dt.timedelta(minutes=1),
        "source_id": "device-1",
        "value_json": {"bpm": 60},
        "ingested_at": T0,
    }
    keys = ["data_type", "start_ts", "end_ts", "source_id"]
    upsert(session, DataPoint, [row], index_elements=keys)
    upsert(session, DataPoint, [{**row, "value_json": {"bpm": 61}}], index_elements=keys)
    session.commit()
    assert _count(session, DataPoint) == 1
    assert session.scalar(select(DataPoint.value_json)) == {"bpm": 61}


def test_large_batches_are_chunked(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(upsert_module, "_MAX_SQL_VARIABLES", 10)  # 5 rows per statement
    assert upsert(session, HrSample, _hr_rows(23, 60), index_elements=["ts"]) == 23
    session.commit()
    assert _count(session, HrSample) == 23

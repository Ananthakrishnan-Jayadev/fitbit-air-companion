from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from fitbit_app.storage.db import create_db_engine
from fitbit_app.storage.migrate import (
    alembic_config,
    current_revision,
    head_revision,
    upgrade_to_head,
)
from fitbit_app.storage.models import Base


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    eng = create_db_engine(tmp_path / "fitbit.db")
    yield eng
    eng.dispose()


def test_upgrade_creates_all_model_tables(engine: Engine) -> None:
    upgrade_to_head(engine)
    tables = set(inspect(engine).get_table_names())
    assert set(Base.metadata.tables) <= tables


def test_migration_matches_models(engine: Engine) -> None:
    """The hand-written migration must produce exactly the schema the models describe."""
    upgrade_to_head(engine)
    with engine.connect() as conn:
        context = MigrationContext.configure(conn, opts={"compare_type": True})
        diffs = compare_metadata(context, Base.metadata)
    assert diffs == []


def test_upgrade_is_idempotent(engine: Engine) -> None:
    upgrade_to_head(engine)
    upgrade_to_head(engine)
    assert current_revision(engine) == head_revision()


def test_revision_tracking(engine: Engine) -> None:
    assert current_revision(engine) is None
    upgrade_to_head(engine)
    assert current_revision(engine) == head_revision() == "0004"


def test_downgrade_to_base_removes_tables(engine: Engine) -> None:
    upgrade_to_head(engine)
    config = alembic_config()
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        command.downgrade(config, "base")
    remaining = set(inspect(engine).get_table_names()) - {"alembic_version"}
    assert remaining == set()


SAMPLE_TABLES = ("hr_samples", "hrv_samples", "spo2_samples", "activity_minutes")

# Synthetic rows, inserted out of order to check the copy keeps every row.
SAMPLE_ROWS = {
    "hr_samples": (
        "(ts, bpm, motion_context) VALUES "
        "('2026-01-02 00:00:05', 61, 'SEDENTARY'), ('2026-01-02 00:00:00', 60, NULL)"
    ),
    "hrv_samples": "(ts, rmssd_ms) VALUES ('2026-01-02 03:00:00', 41.5)",
    "spo2_samples": "(ts, spo2_pct) VALUES ('2026-01-02 03:00:00', 96.0)",
    "activity_minutes": (
        "(ts, steps, activity_level, calories, distance_m) VALUES "
        "('2026-01-02 12:01:00', 90, 'LIGHT', 4.2, 70.0), "
        "('2026-01-02 12:00:00', NULL, NULL, NULL, NULL)"
    ),
}


def _migrate(engine: Engine, action: str, revision: str) -> None:
    config = alembic_config()
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        getattr(command, action)(config, revision)


def _create_sql(engine: Engine, table: str) -> str:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :t"), {"t": table}
        ).scalar_one()


def _dump(engine: Engine) -> dict[str, list[tuple[object, ...]]]:
    with engine.connect() as conn:
        return {
            t: [tuple(r) for r in conn.execute(text(f"SELECT * FROM {t} ORDER BY ts"))]
            for t in SAMPLE_TABLES
        }


def _seed_samples(engine: Engine) -> None:
    with engine.begin() as conn:
        for table, values in SAMPLE_ROWS.items():
            conn.execute(text(f"INSERT INTO {table} {values}"))


def test_sample_tables_are_without_rowid(engine: Engine) -> None:
    upgrade_to_head(engine)
    for table in SAMPLE_TABLES:
        assert "WITHOUT ROWID" in _create_sql(engine, table).upper()
    # The other tables keep their rowid.
    assert "WITHOUT ROWID" not in _create_sql(engine, "daily_metrics").upper()


def test_without_rowid_upgrade_keeps_data(engine: Engine) -> None:
    _migrate(engine, "upgrade", "0003")
    _seed_samples(engine)
    before = _dump(engine)

    _migrate(engine, "upgrade", "0004")

    assert _dump(engine) == before
    assert sum(len(rows) for rows in before.values()) == 6
    # The separate primary-key index (a second copy of every row) is gone.
    assert inspect(engine).get_indexes("hr_samples") == []
    with engine.connect() as conn:
        autoindexes = conn.execute(
            text("SELECT name FROM sqlite_master WHERE name LIKE 'sqlite_autoindex_hr_samples%'")
        ).all()
    assert autoindexes == []


def test_without_rowid_downgrade_keeps_data(engine: Engine) -> None:
    upgrade_to_head(engine)
    _seed_samples(engine)
    before = _dump(engine)

    _migrate(engine, "downgrade", "0003")

    assert _dump(engine) == before
    for table in SAMPLE_TABLES:
        assert "WITHOUT ROWID" not in _create_sql(engine, table).upper()


def test_primary_key_still_rejects_duplicates(engine: Engine) -> None:
    upgrade_to_head(engine)
    _seed_samples(engine)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("INSERT INTO hr_samples (ts, bpm) VALUES ('2026-01-02 00:00:00', 70)"))

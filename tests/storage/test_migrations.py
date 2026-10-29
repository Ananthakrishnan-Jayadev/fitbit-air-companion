from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, inspect

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
    assert current_revision(engine) == head_revision() == "0002"


def test_downgrade_to_base_removes_tables(engine: Engine) -> None:
    upgrade_to_head(engine)
    config = alembic_config()
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        command.downgrade(config, "base")
    remaining = set(inspect(engine).get_table_names()) - {"alembic_version"}
    assert remaining == set()

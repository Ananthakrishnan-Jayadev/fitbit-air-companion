"""Alembic environment.

The app passes an open connection via `config.attributes["connection"]`
(see storage/migrate.py). Developer CLI usage (`alembic revision --autogenerate`) falls
back to the configured database path.
"""

from alembic import context
from sqlalchemy import Connection

from fitbit_app.config import get_settings
from fitbit_app.storage.db import create_db_engine
from fitbit_app.storage.models import Base

config = context.config
target_metadata = Base.metadata


def _run(connection: Connection) -> None:
    # Batch mode lets ALTER-style operations work on SQLite.
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = create_db_engine(get_settings().db_path)
    with engine.begin() as conn:
        _run(conn)
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported")
run_migrations_online()

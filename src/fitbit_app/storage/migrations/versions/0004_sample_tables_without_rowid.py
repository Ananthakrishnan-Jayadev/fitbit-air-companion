"""Rebuild the intraday sample tables as WITHOUT ROWID.

Their primary key is a timestamp, so a normal SQLite table stores every row twice: once in
the rowid table and again in the primary-key index. WITHOUT ROWID keeps a single copy,
clustered by timestamp (about a third of the database for heart rate). No data changes.

SQLite can't toggle ROWID in place, so each table is copied into a new one and renamed.
The space freed by the old tables is reused by future rows; `VACUUM` returns it to the OS.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-02
"""

from collections.abc import Callable, Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Column definitions as they stand after 0003 (factories: a Column can't be reused).
COLUMNS: dict[str, Callable[[], list[sa.Column[Any]]]] = {
    "hr_samples": lambda: [
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("bpm", sa.Integer(), nullable=False),
        sa.Column("motion_context", sa.String(32), nullable=True),
    ],
    "hrv_samples": lambda: [
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("rmssd_ms", sa.Float(), nullable=False),
    ],
    "spo2_samples": lambda: [
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("spo2_pct", sa.Float(), nullable=False),
    ],
    "activity_minutes": lambda: [
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=True),
        sa.Column("activity_level", sa.String(32), nullable=True),
        sa.Column("calories", sa.Float(), nullable=True),
        sa.Column("distance_m", sa.Float(), nullable=True),
    ],
}


def _rebuild(table: str, *, with_rowid: bool) -> None:
    columns = COLUMNS[table]()
    names = ", ".join(c.name for c in columns)
    tmp = f"{table}_rebuild"
    op.create_table(
        tmp,
        *columns,
        sa.PrimaryKeyConstraint("ts", name=f"pk_{table}"),
        sqlite_with_rowid=with_rowid,
    )
    # Inserting in key order keeps the new B-tree compact.
    op.execute(f"INSERT INTO {tmp} ({names}) SELECT {names} FROM {table} ORDER BY ts")
    op.drop_table(table)
    op.rename_table(tmp, table)


def upgrade() -> None:
    for table in COLUMNS:
        _rebuild(table, with_rowid=False)


def downgrade() -> None:
    for table in COLUMNS:
        _rebuild(table, with_rowid=True)

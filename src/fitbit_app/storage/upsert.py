"""Idempotent bulk upserts keyed on natural keys (SQLite ON CONFLICT)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from fitbit_app.storage.models import Base

# SQLite's default max number of bound parameters per statement (3.32+).
_MAX_SQL_VARIABLES = 32766


def upsert(
    session: Session,
    model: type[Base],
    rows: Sequence[Mapping[str, Any]],
    index_elements: Sequence[str],
    update_columns: Sequence[str] | None = None,
) -> int:
    """Insert rows; on conflict with `index_elements`, update `update_columns`.

    `update_columns=None` updates every non-key column present in the rows; an empty
    sequence means "insert or ignore". Returns the number of rows submitted.
    """
    if not rows:
        return 0
    columns = list(rows[0].keys())
    if update_columns is None:
        update_columns = [c for c in columns if c not in index_elements]

    chunk_size = max(1, _MAX_SQL_VARIABLES // len(columns))
    for start in range(0, len(rows), chunk_size):
        stmt = sqlite_insert(model).values(list(rows[start : start + chunk_size]))
        if update_columns:
            stmt = stmt.on_conflict_do_update(
                index_elements=list(index_elements),
                set_={c: stmt.excluded[c] for c in update_columns},
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=list(index_elements))
        session.execute(stmt)
    return len(rows)

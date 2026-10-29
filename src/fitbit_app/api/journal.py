"""/api/journal (daily tags + notes) and /api/correlations ("what affects you")."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from fitbit_app.api.deps import get_session
from fitbit_app.journal import (
    MAX_NOTE_LENGTH,
    PRESET_TAGS,
    effects_for,
    normalize_tags,
    tag_counts,
)
from fitbit_app.storage.models import JournalEntry
from fitbit_app.storage.types import utcnow

router = APIRouter(tags=["journal"])

SessionDep = Annotated[Session, Depends(get_session)]
Outcome = Literal["recovery", "sleep_perf", "hrv_rmssd_ms", "resting_hr", "sleep_min"]
MAX_RANGE_DAYS = 400


class JournalIn(BaseModel):
    tags: list[str] = Field(default_factory=list, max_length=50)
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)


class JournalOut(BaseModel):
    date: dt.date
    tags: list[str]
    note: str | None


class TagInfo(BaseModel):
    tag: str
    count: int
    preset: bool


class EffectOut(BaseModel):
    tag: str
    n_with: int
    n_without: int
    mean_with: float
    mean_without: float
    difference: float
    ci_low: float
    ci_high: float
    confident: bool


class CorrelationsResponse(BaseModel):
    outcome: str
    start: dt.date
    end: dt.date
    logged_days: int
    effects: list[EffectOut]


@router.get("/journal", response_model=list[JournalOut])
def list_entries(session: SessionDep, start: dt.date, end: dt.date) -> list[JournalOut]:
    _check_range(start, end)
    rows = session.scalars(
        select(JournalEntry)
        .where(JournalEntry.date >= start, JournalEntry.date <= end)
        .order_by(JournalEntry.date)
    ).all()
    return [JournalOut(date=r.date, tags=list(r.tags or []), note=r.note) for r in rows]


@router.get("/journal/tags", response_model=list[TagInfo])
def tags(session: SessionDep) -> list[TagInfo]:
    counts = tag_counts(session)
    names = list(PRESET_TAGS) + sorted(t for t in counts if t not in PRESET_TAGS)
    return [TagInfo(tag=t, count=counts.get(t, 0), preset=t in PRESET_TAGS) for t in names]


@router.put("/journal/{date}", response_model=JournalOut)
def put_entry(date: dt.date, body: JournalIn, session: SessionDep) -> JournalOut:
    tag_list = normalize_tags(body.tags)
    note = (body.note or "").strip() or None
    row = session.get(JournalEntry, date)
    if not tag_list and note is None:
        # Empty entry: same as deleting it, so it doesn't count as a "logged" day.
        if row is not None:
            session.delete(row)
            session.commit()
        return JournalOut(date=date, tags=[], note=None)
    if row is None:
        row = JournalEntry(date=date)
        session.add(row)
    row.tags = tag_list
    row.note = note
    row.updated_at = utcnow()
    session.commit()
    return JournalOut(date=date, tags=tag_list, note=note)


@router.delete("/journal/{date}", status_code=204)
def delete_entry(date: dt.date, session: SessionDep) -> None:
    row = session.get(JournalEntry, date)
    if row is not None:
        session.delete(row)
        session.commit()


@router.get("/correlations", response_model=CorrelationsResponse)
def correlations(
    session: SessionDep,
    outcome: Outcome = "recovery",
    days: Annotated[int, Query(ge=14, le=MAX_RANGE_DAYS)] = 180,
    end: dt.date | None = None,
) -> CorrelationsResponse:
    last = end or dt.date.today()
    start = last - dt.timedelta(days=days - 1)
    effects, logged = effects_for(session, outcome, start, last)
    return CorrelationsResponse(
        outcome=outcome,
        start=start,
        end=last,
        logged_days=logged,
        effects=[EffectOut(**e.__dict__, confident=e.confident) for e in effects],
    )


def _check_range(start: dt.date, end: dt.date) -> None:
    if end < start or (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(400, f"Invalid range (max {MAX_RANGE_DAYS} days)")

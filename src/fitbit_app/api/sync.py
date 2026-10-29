"""POST /api/sync (trigger) and GET /api/sync/status."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from fitbit_app.api.deps import get_session, get_settings_dep, get_sync_service
from fitbit_app.config import Settings
from fitbit_app.ingest.registry import select_specs
from fitbit_app.ingest.service import SyncService
from fitbit_app.storage.models import SyncState

router = APIRouter(prefix="/sync", tags=["sync"])

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SyncDep = Annotated[SyncService, Depends(get_sync_service)]


class SyncRequest(BaseModel):
    types: list[str] | None = None
    since: dt.date | None = None


class SyncStarted(BaseModel):
    started: bool


class TypeStatus(BaseModel):
    key: str
    kind: str
    cursor: dt.datetime | None = None
    synced_from: dt.datetime | None = None
    last_success_at: dt.datetime | None = None
    last_error: str | None = None
    last_error_at: dt.datetime | None = None


class LastRun(BaseModel):
    started_at: dt.datetime
    finished_at: dt.datetime | None
    ok: list[str]
    failed: dict[str, str]
    points: dict[str, int]


class SyncStatus(BaseModel):
    running: bool
    last_run: LastRun | None
    last_error: str | None
    types: list[TypeStatus]


@router.post("", response_model=SyncStarted, status_code=202)
async def trigger(body: SyncRequest, settings: SettingsDep, sync_service: SyncDep) -> SyncStarted:
    # async: start_background needs the running event loop.
    try:
        select_specs(include_beta=settings.enable_beta_types, keys=body.types)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if await asyncio.to_thread(sync_service.token_store.load) is None:
        raise HTTPException(400, "Google account not connected")
    if not sync_service.start_background(keys=body.types, since=body.since):
        raise HTTPException(409, "A sync is already running")
    return SyncStarted(started=True)


@router.get("/status", response_model=SyncStatus)
def status(session: SessionDep, settings: SettingsDep, sync_service: SyncDep) -> SyncStatus:
    states = {s.data_type: s for s in session.scalars(select(SyncState))}
    types = []
    for spec in select_specs(include_beta=settings.enable_beta_types):
        state = states.get(spec.key)
        types.append(
            TypeStatus(
                key=spec.key,
                kind=spec.kind.value,
                cursor=state.cursor if state else None,
                synced_from=state.synced_from if state else None,
                last_success_at=state.last_success_at if state else None,
                last_error=state.last_error if state else None,
                last_error_at=state.last_error_at if state else None,
            )
        )
    report = sync_service.last_report
    last_run = None
    if report is not None:
        last_run = LastRun(
            started_at=report.started_at,
            finished_at=report.finished_at,
            ok=report.ok,
            failed=report.failed,
            points=report.points,
        )
    return SyncStatus(
        running=sync_service.running,
        last_run=last_run,
        last_error=sync_service.last_error,
        types=types,
    )

"""FastAPI dependencies. DB sessions are sync: use them from `def` handlers only."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from fitbit_app.config import Settings
from fitbit_app.ingest.service import SyncService


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_sync_service(request: Request) -> SyncService:
    return request.app.state.sync_service

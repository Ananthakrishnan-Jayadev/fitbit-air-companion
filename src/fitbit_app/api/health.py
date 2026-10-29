"""GET /api/health: overall app status for the UI banner and `doctor`."""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from fitbit_app import __version__
from fitbit_app.ai.status import OllamaStatus, check_ollama
from fitbit_app.config import Settings
from fitbit_app.storage.db import ping

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class ComponentStatus(BaseModel):
    ok: bool
    detail: str | None = None


class GoogleStatus(BaseModel):
    configured: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: ComponentStatus
    ai_enabled: bool
    ollama: OllamaStatus | None
    google: GoogleStatus


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings: Settings = request.app.state.settings

    try:
        await asyncio.to_thread(ping, request.app.state.engine)
        database = ComponentStatus(ok=True)
    except SQLAlchemyError as exc:
        logger.error("Database health check failed: %s", type(exc).__name__)
        database = ComponentStatus(ok=False, detail="Database unavailable")

    ollama: OllamaStatus | None = None
    if settings.ai_enabled:
        ollama = await check_ollama(settings.ollama_host, settings.ollama_model)

    ai_ok = ollama is None or (ollama.reachable and ollama.model_present)
    return HealthResponse(
        status="ok" if database.ok and ai_ok else "degraded",
        version=__version__,
        database=database,
        ai_enabled=settings.ai_enabled,
        ollama=ollama,
        google=GoogleStatus(configured=settings.google_configured),
    )

"""GET /api/export: download a ZIP of CSV files."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from fitbit_app.config import Settings
from fitbit_app.storage.export import write_export
from fitbit_app.storage.types import utcnow

router = APIRouter(tags=["export"])


@router.get("/export", response_class=FileResponse)
async def export(request: Request, intraday: bool = False) -> FileResponse:
    settings: Settings = request.app.state.settings
    path = await asyncio.to_thread(_build, request, settings, intraday)
    name = f"fitbit-export-{utcnow():%Y%m%d}{'-intraday' if intraday else ''}.zip"
    return FileResponse(
        path,
        media_type="application/zip",
        filename=name,
        background=BackgroundTask(path.unlink, missing_ok=True),
    )


def _build(request: Request, settings: Settings, intraday: bool) -> Path:
    # Temp file inside the private data dir, not /tmp, since it contains health data.
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="export-", suffix=".zip", dir=settings.data_dir)
    path = Path(name)
    try:
        with os.fdopen(fd, "wb") as target, request.app.state.session_factory() as session:
            write_export(session, target, include_intraday=intraday)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path

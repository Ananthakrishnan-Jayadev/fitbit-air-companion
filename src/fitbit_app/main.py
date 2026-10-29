"""FastAPI app factory: API routers, lifespan (DB + migrations), and the built React app."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

from fitbit_app import __version__
from fitbit_app.api import auth, health, profile, sync
from fitbit_app.config import Settings, get_settings
from fitbit_app.ingest.service import SyncService
from fitbit_app.scheduler import create_scheduler
from fitbit_app.storage.db import create_db_engine, create_session_factory
from fitbit_app.storage.migrate import upgrade_to_head

logger = logging.getLogger(__name__)

UI_NOT_BUILT_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>UI not built</title></head>
<body style="font-family: system-ui, sans-serif; max-width: 40rem; margin: 4rem auto;">
<h1>UI not built</h1>
<p>The API is running, but the frontend has not been built yet. Run:</p>
<pre>.venv/bin/fitbit build-ui</pre>
<p>or use <code>.venv/bin/fitbit serve --dev</code> for the hot-reload dev UI.</p>
</body></html>"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_db_engine(settings.db_path)
        await asyncio.to_thread(upgrade_to_head, engine)
        session_factory = create_session_factory(engine)
        sync_service = SyncService(settings, session_factory)
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.sync_service = sync_service
        app.state.oauth_pending = {}
        logger.info("Database ready at %s", settings.db_path)

        scheduler = None
        if settings.scheduler_enabled and settings.google_configured:
            scheduler = create_scheduler(settings, sync_service)
            scheduler.start()
            logger.info("Background sync every %d min", settings.sync_interval_min)
        try:
            yield
        finally:
            if scheduler is not None:
                scheduler.shutdown(wait=False)
            await sync_service.shutdown()
            engine.dispose()

    app = FastAPI(title="Fitbit Air Companion", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    for module in (health, auth, sync, profile):
        app.include_router(module.router, prefix="/api")
    _mount_frontend(app, settings.static_dir)
    return app


def _mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Serve built files, falling back to index.html so client-side routes work."""
    static_root = static_dir.resolve()
    index = static_root / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> Response:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        if not index.is_file():
            return HTMLResponse(UI_NOT_BUILT_HTML, status_code=503)
        if full_path:
            candidate = (static_root / full_path).resolve()
            if candidate.is_relative_to(static_root) and candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(index)

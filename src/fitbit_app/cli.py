"""`fitbit` command-line entry point."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from typing import Annotated

import typer
import uvicorn

from fitbit_app.config import get_settings
from fitbit_app.devserver import VITE_URL, start_vite, stop_vite
from fitbit_app.doctor import Level, run_checks
from fitbit_app.errors import ConfigError
from fitbit_app.logging_setup import configure_logging
from fitbit_app.main import create_app
from fitbit_app.storage.db import create_db_engine
from fitbit_app.storage.migrate import upgrade_to_head

app = typer.Typer(no_args_is_help=True, help="Fitbit Air companion app.")
db_app = typer.Typer(no_args_is_help=True, help="Database commands.")
app.add_typer(db_app, name="db")

_LEVEL_COLORS = {
    Level.OK: typer.colors.GREEN,
    Level.WARN: typer.colors.YELLOW,
    Level.FAIL: typer.colors.RED,
}


@app.command()
def serve(
    host: Annotated[str | None, typer.Option(help="Bind address (default from .env)")] = None,
    port: Annotated[int | None, typer.Option(help="Port (default from .env)")] = None,
    dev: Annotated[bool, typer.Option("--dev", help="Also run the Vite dev server")] = False,
) -> None:
    """Run the API, UI and background jobs in this terminal."""
    settings = get_settings()
    configure_logging(settings.log_level)
    host = host or settings.host
    port = port or settings.port

    vite = None
    if dev:
        try:
            vite = start_vite(settings.frontend_dir, api_port=port)
        except ConfigError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from exc
        typer.secho(f"Dev UI (hot reload): {VITE_URL}", fg=typer.colors.CYAN)
    elif not (settings.static_dir / "index.html").is_file():
        typer.secho(
            "UI not built yet; run `fitbit build-ui` (API still works).", fg=typer.colors.YELLOW
        )

    typer.secho(f"App: http://{host}:{port}", fg=typer.colors.CYAN)
    try:
        uvicorn.run(create_app(settings), host=host, port=port, log_config=None)
    finally:
        if vite is not None:
            stop_vite(vite)


@app.command("build-ui")
def build_ui() -> None:
    """Build the React app into the Python package (src/fitbit_app/static)."""
    settings = get_settings()
    npm = shutil.which("npm")
    if npm is None:
        typer.secho("npm not found on PATH; install Node.js first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    if not (settings.frontend_dir / "node_modules").is_dir():
        typer.secho(
            f"Frontend dependencies missing. Run: npm --prefix {settings.frontend_dir} install",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    result = subprocess.run([npm, "run", "build"], cwd=settings.frontend_dir, check=False)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)
    typer.secho(f"UI built into {settings.static_dir}", fg=typer.colors.GREEN)


@app.command()
def doctor() -> None:
    """Check configuration, database, UI build and Ollama."""
    settings = get_settings()
    results = asyncio.run(run_checks(settings))
    for result in results:
        tag = typer.style(f"[{result.level.value:>4}]", fg=_LEVEL_COLORS[result.level], bold=True)
        typer.echo(f"{tag} {result.name}: {result.detail}")
    if any(r.level is Level.FAIL for r in results):
        raise typer.Exit(1)


@db_app.command("upgrade")
def db_upgrade() -> None:
    """Apply database migrations."""
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_db_engine(settings.db_path)
    try:
        upgrade_to_head(engine)
    finally:
        engine.dispose()
    typer.secho(f"Database up to date: {settings.db_path}", fg=typer.colors.GREEN)


def _not_yet(phase: int) -> None:
    typer.secho(f"Not implemented yet (Phase {phase}).", fg=typer.colors.YELLOW)
    raise typer.Exit(1)


@app.command()
def sync() -> None:
    """Sync data from the Google Health API (Phase 2)."""
    _not_yet(2)


@app.command()
def analyze() -> None:
    """Recompute scores (Phase 3)."""
    _not_yet(3)


@app.command()
def brief() -> None:
    """Regenerate the AI daily brief (Phase 4)."""
    _not_yet(4)

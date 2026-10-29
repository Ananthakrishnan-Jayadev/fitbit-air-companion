"""`fitbit` command-line entry point."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import shutil
import subprocess
from typing import Annotated

import typer
import uvicorn

from fitbit_app.ai.context import latest_scored_day
from fitbit_app.ai.service import KINDS, AIService
from fitbit_app.config import Settings, get_settings
from fitbit_app.devserver import VITE_URL, start_vite, stop_vite
from fitbit_app.doctor import Level, run_checks
from fitbit_app.errors import ConfigError, FitbitAppError
from fitbit_app.ingest.registry import select_specs
from fitbit_app.ingest.service import SyncService
from fitbit_app.ingest.sync import SyncReport
from fitbit_app.logging_setup import configure_logging
from fitbit_app.main import create_app
from fitbit_app.scoring import ScoreService
from fitbit_app.storage.db import create_db_engine, create_session_factory
from fitbit_app.storage.migrate import upgrade_to_head
from fitbit_app.storage.normalize import renormalize

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


@db_app.command("renormalize")
def db_renormalize(
    types: Annotated[
        str | None, typer.Option(help="Comma-separated data types (default: all with raw JSON)")
    ] = None,
) -> None:
    """Rebuild typed tables from stored raw JSON (no download)."""
    settings = get_settings()
    configure_logging(settings.log_level)
    keys = [t.strip() for t in types.split(",") if t.strip()] if types else None
    try:
        specs = select_specs(include_beta=settings.enable_beta_types, keys=keys)
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    engine = create_db_engine(settings.db_path)
    try:
        upgrade_to_head(engine)
        with create_session_factory(engine)() as session:
            for spec in specs:
                count = renormalize(session, spec)
                session.commit()
                if count:
                    typer.echo(f"  {spec.key}: {count} points")
    finally:
        engine.dispose()
    typer.secho("Typed tables rebuilt from raw data.", fg=typer.colors.GREEN)


@app.command()
def sync(
    since: Annotated[
        dt.datetime | None,
        typer.Option(formats=["%Y-%m-%d"], help="Backfill back to this date (YYYY-MM-DD)"),
    ] = None,
    types: Annotated[
        str | None, typer.Option(help="Comma-separated data types, e.g. heart-rate,sleep")
    ] = None,
) -> None:
    """Sync data from the Google Health API now (the server also syncs on a schedule)."""
    settings = get_settings()
    configure_logging(settings.log_level)
    keys = [t.strip() for t in types.split(",") if t.strip()] if types else None
    try:
        report = asyncio.run(_run_sync(settings, keys, since.date() if since else None))
    except (FitbitAppError, ValueError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    total = sum(report.points.values())
    typer.secho(f"Synced {len(report.ok)} data types, {total} points.", fg=typer.colors.GREEN)
    for key, message in report.failed.items():
        typer.secho(f"  failed {key}: {message}", fg=typer.colors.RED)
    if report.failed:
        raise typer.Exit(1)


async def _run_sync(
    settings: Settings, keys: list[str] | None, since: dt.date | None
) -> SyncReport:
    engine = create_db_engine(settings.db_path)
    try:
        await asyncio.to_thread(upgrade_to_head, engine)
        session_factory = create_session_factory(engine)
        scores = ScoreService(session_factory)

        async def rescore(_: object) -> None:
            await asyncio.to_thread(scores.recompute_after_sync)

        service = SyncService(settings, session_factory, after_sync=rescore)
        return await service.run(keys=keys, since=since)
    finally:
        engine.dispose()


@app.command()
def analyze(
    day: Annotated[
        dt.datetime | None,
        typer.Option("--date", formats=["%Y-%m-%d"], help="Score only this day (YYYY-MM-DD)"),
    ] = None,
    all_days: Annotated[bool, typer.Option("--all", help="Rescore every day with data")] = False,
) -> None:
    """Recompute scores, baselines and derived daily values from stored data."""
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_db_engine(settings.db_path)
    try:
        upgrade_to_head(engine)
        service = ScoreService(create_session_factory(engine))
        if day is not None:
            count = service.recompute([day.date()])
        elif all_days:
            count = service.recompute_all()
        else:
            count = service.recompute_after_sync()
    finally:
        engine.dispose()
    typer.secho(f"Scored {count} days.", fg=typer.colors.GREEN)


@app.command()
def brief(
    day: Annotated[
        dt.datetime | None,
        typer.Option("--date", formats=["%Y-%m-%d"], help="Day (default: latest scored day)"),
    ] = None,
    kind: Annotated[str, typer.Option(help=f"One of: {', '.join(KINDS)}")] = "daily_brief",
    force: Annotated[bool, typer.Option("--force", help="Regenerate even if unchanged")] = False,
) -> None:
    """Generate an AI insight with the local model and print it."""
    if kind not in KINDS:
        typer.secho(f"--kind must be one of: {', '.join(KINDS)}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_db_engine(settings.db_path)
    try:
        upgrade_to_head(engine)
        session_factory = create_session_factory(engine)
        with session_factory() as session:
            target = day.date() if day else latest_scored_day(session)
        if target is None:
            typer.secho("No scored days yet; run `fitbit analyze` first.", fg=typer.colors.RED)
            raise typer.Exit(1)
        service = AIService(settings, session_factory)
        try:
            insight = asyncio.run(service.generate(kind, target, force=force))
        except FitbitAppError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from exc
    finally:
        engine.dispose()
    if insight is None:
        typer.secho(f"Not enough data for a {kind} on {target}.", fg=typer.colors.YELLOW)
        raise typer.Exit(1)
    typer.secho(f"{kind} for {target} ({insight.model})", bold=True)
    typer.echo(json.dumps(insight.content, indent=2, ensure_ascii=False))

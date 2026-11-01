import datetime as dt

import pytest
from typer.testing import CliRunner

from fitbit_app import cli as cli_module
from fitbit_app import devserver
from fitbit_app.ai.status import OllamaStatus
from fitbit_app.config import Settings
from fitbit_app.storage.db import create_db_engine, create_session_factory
from fitbit_app.storage.migrate import current_revision, head_revision, upgrade_to_head
from fitbit_app.storage.models import SyncState

runner = CliRunner()


@pytest.fixture(autouse=True)
def _use_test_settings(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_module, "get_settings", lambda: settings)


def test_doctor_exits_zero_with_only_warnings() -> None:
    result = runner.invoke(cli_module.app, ["doctor"])
    assert result.exit_code == 0
    assert "[warn] Database" in result.output


def test_doctor_does_not_call_real_ollama_when_enabled(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake(host: str, model: str) -> OllamaStatus:
        return OllamaStatus(reachable=False, model=model, model_present=False, detail="down")

    monkeypatch.setattr("fitbit_app.doctor.check_ollama", fake)
    monkeypatch.setattr(
        cli_module, "get_settings", lambda: settings.model_copy(update={"ai_enabled": True})
    )
    result = runner.invoke(cli_module.app, ["doctor"])
    assert result.exit_code == 0
    assert "[warn] Ollama: down" in result.output


def test_db_upgrade(settings: Settings) -> None:
    result = runner.invoke(cli_module.app, ["db", "upgrade"])
    assert result.exit_code == 0
    engine = create_db_engine(settings.db_path)
    try:
        assert current_revision(engine) == head_revision()
    finally:
        engine.dispose()


def test_brief_needs_scored_days() -> None:
    result = runner.invoke(cli_module.app, ["brief"])
    assert result.exit_code == 1
    assert "No scored days yet" in result.output


def test_brief_rejects_unknown_kind() -> None:
    result = runner.invoke(cli_module.app, ["brief", "--kind", "poem"])
    assert result.exit_code == 1


@pytest.mark.parametrize(
    "args", [["analyze"], ["analyze", "--all"], ["analyze", "--date", "2026-10-01"]]
)
def test_analyze_on_empty_database(args: list[str]) -> None:
    result = runner.invoke(cli_module.app, args)
    assert result.exit_code == 0
    assert "Scored 0 days" in result.output


def test_db_renormalize(settings: Settings) -> None:
    result = runner.invoke(cli_module.app, ["db", "renormalize", "--types", "steps:daily"])
    assert result.exit_code == 0
    assert "rebuilt" in result.output


def test_db_renormalize_rejects_unknown_types() -> None:
    result = runner.invoke(cli_module.app, ["db", "renormalize", "--types", "nope"])
    assert result.exit_code == 1


def test_sync_without_connection_fails_cleanly() -> None:
    result = runner.invoke(cli_module.app, ["sync"])
    assert result.exit_code == 1
    assert "No Google account connected" in result.output


def test_sync_reset_clears_progress_for_selected_types(settings: Settings) -> None:
    engine = create_db_engine(settings.db_path)
    upgrade_to_head(engine)
    stamp = dt.datetime(2026, 10, 1, tzinfo=dt.UTC)
    with create_session_factory(engine)() as session:
        for key in ("weight", "body-fat", "steps"):
            session.add(SyncState(data_type=key, cursor=stamp, synced_from=stamp))
        session.commit()

    # The sync itself then fails (not connected), but the reset has already happened.
    result = runner.invoke(cli_module.app, ["sync", "--types", "weight,body-fat", "--reset"])
    assert "Reset sync progress for: weight, body-fat" in result.output
    with create_session_factory(engine)() as session:
        remaining = {s.data_type for s in session.query(SyncState).all()}
    engine.dispose()
    assert remaining == {"steps"}


def test_sync_reset_requires_types() -> None:
    result = runner.invoke(cli_module.app, ["sync", "--reset"])
    assert result.exit_code == 1
    assert "--reset needs --types" in result.output


def test_sync_rejects_unknown_types() -> None:
    result = runner.invoke(cli_module.app, ["sync", "--types", "steps,nope"])
    assert result.exit_code == 1
    assert "nope" in result.output


def test_serve_dev_without_npm_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(devserver.shutil, "which", lambda _name: None)

    def must_not_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("uvicorn must not start")

    monkeypatch.setattr(cli_module.uvicorn, "run", must_not_run)
    result = runner.invoke(cli_module.app, ["serve", "--dev"])
    assert result.exit_code == 1


def test_build_ui_without_npm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: None)
    result = runner.invoke(cli_module.app, ["build-ui"])
    assert result.exit_code == 1

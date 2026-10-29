import datetime as dt
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from pydantic import SecretStr

from fitbit_app import doctor as doctor_module
from fitbit_app.ai.status import OllamaStatus
from fitbit_app.config import Settings
from fitbit_app.doctor import CheckResult, Level, run_checks
from fitbit_app.ingest.oauth import TokenSet, TokenStore
from fitbit_app.storage.db import create_db_engine, create_session_factory
from fitbit_app.storage.migrate import upgrade_to_head


def _by_name(results: list[CheckResult]) -> dict[str, CheckResult]:
    return {r.name: r for r in results}


def _fake_ollama(reachable: bool, present: bool) -> Callable[[str, str], Awaitable[OllamaStatus]]:
    async def fake(host: str, model: str) -> OllamaStatus:
        detail = None if present else "x"
        return OllamaStatus(reachable=reachable, model=model, model_present=present, detail=detail)

    return fake


async def test_fresh_setup_only_warns(settings: Settings) -> None:
    results = _by_name(await run_checks(settings))
    assert all(r.level is not Level.FAIL for r in results.values())
    assert results[".env"].level is Level.WARN
    assert results["Google OAuth"].level is Level.WARN
    assert results["Database"].level is Level.WARN
    assert results["Google connection"].level is Level.WARN
    assert results["Frontend build"].level is Level.WARN
    assert results["Ollama"].level is Level.WARN  # AI disabled in the fixture


async def test_fully_configured_is_ok(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("")
    (settings.static_dir / "index.html").write_text("<html></html>")
    engine = create_db_engine(settings.db_path)
    upgrade_to_head(engine)
    TokenStore(create_session_factory(engine), settings.fitbit_secret_key).save(
        TokenSet("a", "r", dt.datetime(2030, 1, 1, tzinfo=dt.UTC), "", "Bearer")
    )
    engine.dispose()
    monkeypatch.setattr(doctor_module, "check_ollama", _fake_ollama(True, True))
    configured = settings.model_copy(
        update={
            "ai_enabled": True,
            "google_client_id": "id",
            "google_client_secret": SecretStr("secret"),
            "fitbit_secret_key": SecretStr("key"),
        }
    )

    results = await run_checks(configured)
    assert [r for r in results if r.level is not Level.OK] == []


async def test_unmigrated_database_warns(settings: Settings) -> None:
    create_db_engine(settings.db_path).dispose()
    result = _by_name(await run_checks(settings))["Database"]
    assert result.level is Level.WARN
    assert "fitbit db upgrade" in result.detail


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
async def test_unwritable_database_fails(settings: Settings) -> None:
    create_db_engine(settings.db_path).dispose()
    settings.db_path.chmod(0o400)
    try:
        assert _by_name(await run_checks(settings))["Database"].level is Level.FAIL
    finally:
        settings.db_path.chmod(0o600)


@pytest.mark.parametrize(("reachable", "present"), [(False, False), (True, False)])
async def test_ollama_problems_are_warnings(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, reachable: bool, present: bool
) -> None:
    monkeypatch.setattr(doctor_module, "check_ollama", _fake_ollama(reachable, present))
    enabled = settings.model_copy(update={"ai_enabled": True})
    assert _by_name(await run_checks(enabled))["Ollama"].level is Level.WARN

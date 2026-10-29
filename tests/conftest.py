from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.config import Settings, get_settings
from fitbit_app.main import create_app
from fitbit_app.storage.db import create_db_engine, create_session_factory
from fitbit_app.storage.migrate import upgrade_to_head

_SETTINGS_ENV_VARS = [name.upper() for name in Settings.model_fields]


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Keep the developer's shell env and repo .env out of every test."""
    for name in _SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        static_dir=static_dir,
        frontend_dir=tmp_path / "frontend",
        ai_enabled=False,
        scheduler_enabled=False,
        fitbit_secret_key=Fernet.generate_key().decode(),
    )


@pytest.fixture
def google_settings(settings: Settings) -> Settings:
    """Settings with a (fake) Google OAuth client configured."""
    return settings.model_copy(
        update={
            "google_client_id": "test-client-id",
            "google_client_secret": SecretStr("test-client-secret"),
        }
    )


@pytest.fixture
def session_factory(settings: Settings) -> Iterator[sessionmaker[Session]]:
    engine = create_db_engine(settings.db_path)
    upgrade_to_head(engine)
    yield create_session_factory(engine)
    engine.dispose()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client

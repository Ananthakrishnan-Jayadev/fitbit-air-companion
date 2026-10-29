from pathlib import Path

import pytest

from fitbit_app.config import Settings, get_settings


def test_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.ollama_model == "qwen3.5:9b"
    assert settings.ai_enabled is True
    assert settings.google_configured is False


def test_db_path_is_inside_data_dir(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path)
    assert settings.db_path == tmp_path / "fitbit.db"


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "9001")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("AI_ENABLED", "false")
    settings = Settings(_env_file=None)
    assert settings.port == 9001
    assert settings.ollama_model == "qwen2.5:7b"
    assert settings.ai_enabled is False


def test_reads_env_file_from_working_directory(tmp_path: Path) -> None:
    # conftest chdirs into tmp_path.
    (tmp_path / ".env").write_text("GOOGLE_CLIENT_ID=abc\nGOOGLE_CLIENT_SECRET=xyz\n")
    settings = Settings()
    assert settings.google_configured is True
    assert settings.google_client_secret.get_secret_value() == "xyz"


def test_secrets_are_not_exposed_in_repr() -> None:
    settings = Settings(_env_file=None, google_client_secret="super-secret")
    assert "super-secret" not in repr(settings)


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()

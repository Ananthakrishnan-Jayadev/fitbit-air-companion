"""Typed application settings. The only place that reads environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_DIR = Path(__file__).resolve().parent
ENV_FILE = Path(".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    data_dir: Path = Path("data")
    static_dir: Path = PACKAGE_DIR / "static"
    # Editable (src-layout) install: repo_root/src/fitbit_app -> repo_root/frontend
    frontend_dir: Path = PACKAGE_DIR.parents[1] / "frontend"

    # Google Health API
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    fitbit_secret_key: SecretStr = SecretStr("")

    # Sync
    sync_interval_min: int = 15

    # Local AI
    ai_enabled: bool = True
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3.5:9b"
    ollama_fallback_model: str | None = None
    ollama_timeout_s: float = 300.0
    ollama_num_ctx: int = 16384

    @property
    def db_path(self) -> Path:
        return self.data_dir / "fitbit.db"

    @property
    def google_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()

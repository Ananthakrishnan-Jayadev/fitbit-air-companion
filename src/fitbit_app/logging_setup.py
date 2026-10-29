"""Console (+ optional rotating file) logging. Uvicorn logs propagate here (log_config=None)."""

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
LOG_FILE = "fitbit.log"
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUPS = 3

# Per-request lines from these are noise (hundreds per backfill, Ollama polls every 30 s).
QUIET_LOGGERS = ("httpx", "apscheduler.executors.default")

_SECRET_QUERY = re.compile(r"([?&](?:code|state)=)[^&\s]+")


class RedactOAuthParams(logging.Filter):
    """Mask OAuth `code`/`state` query values in uvicorn access log lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                _SECRET_QUERY.sub(r"\1[redacted]", arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True


def configure_logging(level: str = "INFO", log_dir: Path | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        handlers.append(
            RotatingFileHandler(
                log_dir / LOG_FILE,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUPS,
                encoding="utf-8",
            )
        )
    logging.basicConfig(level=level.upper(), format=LOG_FORMAT, handlers=handlers, force=True)
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, RedactOAuthParams) for f in access.filters):
        access.addFilter(RedactOAuthParams())

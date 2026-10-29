"""Console logging. Uvicorn's loggers propagate here because serve passes log_config=None."""

import logging
import re

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

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


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level.upper(), format=LOG_FORMAT, force=True)
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, RedactOAuthParams) for f in access.filters):
        access.addFilter(RedactOAuthParams())

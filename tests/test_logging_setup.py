import logging
from collections.abc import Iterator

import pytest

from fitbit_app.logging_setup import QUIET_LOGGERS, RedactOAuthParams, configure_logging


def _access_record(path: str) -> logging.LogRecord:
    # Same shape as uvicorn's access log: (client, method, path, http version, status).
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:5000", "GET", path, "1.1", 303),
        None,
    )


def test_redacts_oauth_code_and_state() -> None:
    record = _access_record("/api/auth/callback?state=abc123&iss=x&code=4/0SECRET&scope=s")
    RedactOAuthParams().filter(record)
    message = record.getMessage()
    assert "4/0SECRET" not in message
    assert "abc123" not in message
    assert "code=[redacted]" in message
    assert "state=[redacted]" in message
    assert "iss=x" in message


def test_leaves_other_paths_alone() -> None:
    record = _access_record("/api/sync/status")
    RedactOAuthParams().filter(record)
    assert "/api/sync/status" in record.getMessage()


@pytest.fixture
def restore_logging() -> Iterator[None]:
    access = logging.getLogger("uvicorn.access")
    levels = {name: logging.getLogger(name).level for name in QUIET_LOGGERS}
    filters = list(access.filters)
    yield
    for name, level in levels.items():
        logging.getLogger(name).setLevel(level)
    access.filters = filters


@pytest.mark.usefixtures("restore_logging")
def test_configure_logging_quiets_noise_and_installs_filter_once() -> None:
    configure_logging("INFO")
    configure_logging("INFO")
    assert all(logging.getLogger(n).level == logging.WARNING for n in QUIET_LOGGERS)
    access_filters = logging.getLogger("uvicorn.access").filters
    assert sum(isinstance(f, RedactOAuthParams) for f in access_filters) == 1

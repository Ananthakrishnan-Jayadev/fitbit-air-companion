from pydantic import SecretStr

from fitbit_app.config import Settings
from fitbit_app.login import (
    FAILURE_WINDOW_S,
    MAX_FAILURES,
    LoginThrottle,
    issue_token,
    password_matches,
    token_valid,
)

NOW = 1_800_000_000.0
DAY = 86_400


def _with_password(settings: Settings, password: str = "correct horse") -> Settings:
    return settings.model_copy(update={"app_password": SecretStr(password)})


def test_login_required_only_with_password(settings: Settings) -> None:
    assert not settings.login_required
    assert _with_password(settings).login_required


def test_listens_beyond_loopback(settings: Settings) -> None:
    assert not settings.listens_beyond_loopback
    assert settings.model_copy(update={"host": "0.0.0.0"}).listens_beyond_loopback


def test_password_matches(settings: Settings) -> None:
    protected = _with_password(settings)
    assert password_matches(protected, "correct horse")
    assert not password_matches(protected, "correct horse ")
    assert not password_matches(protected, "")


def test_empty_password_never_matches(settings: Settings) -> None:
    assert not password_matches(settings, "")


def test_token_roundtrip(settings: Settings) -> None:
    protected = _with_password(settings)
    token = issue_token(protected, now=NOW)
    assert token_valid(protected, token, now=NOW + 60)


def test_token_expires(settings: Settings) -> None:
    protected = _with_password(settings).model_copy(update={"session_days": 30})
    token = issue_token(protected, now=NOW)
    assert token_valid(protected, token, now=NOW + 30 * DAY)
    assert not token_valid(protected, token, now=NOW + 30 * DAY + 1)


def test_token_from_the_future_rejected(settings: Settings) -> None:
    protected = _with_password(settings)
    assert not token_valid(protected, issue_token(protected, now=NOW + 3600), now=NOW)


def test_changing_password_invalidates_tokens(settings: Settings) -> None:
    token = issue_token(_with_password(settings, "old"), now=NOW)
    assert not token_valid(_with_password(settings, "new"), token, now=NOW)


def test_changing_secret_key_invalidates_tokens(settings: Settings) -> None:
    protected = _with_password(settings)
    token = issue_token(protected, now=NOW)
    other = protected.model_copy(update={"fitbit_secret_key": SecretStr("another-key")})
    assert not token_valid(other, token, now=NOW)


def test_tampered_tokens_rejected(settings: Settings) -> None:
    protected = _with_password(settings)
    issued, _, signature = issue_token(protected, now=NOW).partition(".")
    for bad in [
        None,
        "",
        "garbage",
        f"{issued}.",
        f".{signature}",
        f"{int(issued) + 1}.{signature}",
        f"{issued}.{signature[:-1]}0",
        f"-{issued}.{signature}",
    ]:
        assert not token_valid(protected, bad, now=NOW), bad


def test_throttle_blocks_after_max_failures_then_recovers() -> None:
    now = [0.0]
    throttle = LoginThrottle(clock=lambda: now[0])
    for _ in range(MAX_FAILURES - 1):
        throttle.record_failure()
    assert not throttle.blocked()
    throttle.record_failure()
    assert throttle.blocked()

    now[0] += FAILURE_WINDOW_S + 1
    assert not throttle.blocked()


def test_throttle_reset() -> None:
    throttle = LoginThrottle(clock=lambda: 0.0)
    for _ in range(MAX_FAILURES):
        throttle.record_failure()
    throttle.reset()
    assert not throttle.blocked()

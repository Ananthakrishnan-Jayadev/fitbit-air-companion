"""Optional single-password login for the web UI and API.

Enabled by setting APP_PASSWORD (e.g. when the app is reachable from the home network).
A successful login sets an HttpOnly cookie holding a signed issue time; nothing is stored
server-side. The signing key is derived from FITBIT_SECRET_KEY *and* the password, so
changing the password signs every device out.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections import deque
from collections.abc import Callable

from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from fitbit_app.config import Settings

COOKIE_NAME = "fitbit_session"

# Reachable without a session: status for the UI, the login form itself, and the health
# endpoint (Docker healthcheck; it holds no health data).
PUBLIC_PATHS = frozenset(
    {"/api/health", "/api/session", "/api/session/login", "/api/session/logout"}
)

MAX_FAILURES = 5
FAILURE_WINDOW_S = 60.0


def _signing_key(settings: Settings) -> bytes:
    material = b"\0".join(
        [
            b"fitbit-app session v1",
            settings.fitbit_secret_key.get_secret_value().encode(),
            settings.app_password.get_secret_value().encode(),
        ]
    )
    return hashlib.sha256(material).digest()


def _sign(key: bytes, issued: int) -> str:
    return hmac.new(key, str(issued).encode(), hashlib.sha256).hexdigest()


def password_matches(settings: Settings, candidate: str) -> bool:
    expected = settings.app_password.get_secret_value()
    return bool(expected) and hmac.compare_digest(candidate.encode(), expected.encode())


def issue_token(settings: Settings, now: float | None = None) -> str:
    issued = int(time.time() if now is None else now)
    return f"{issued}.{_sign(_signing_key(settings), issued)}"


def token_valid(settings: Settings, token: str | None, now: float | None = None) -> bool:
    """True if `token` was issued by `issue_token` with the current secrets and hasn't expired."""
    if not token:
        return False
    issued_text, _, signature = token.partition(".")
    if not issued_text.isdigit():
        return False
    issued = int(issued_text)
    if not hmac.compare_digest(signature, _sign(_signing_key(settings), issued)):
        return False
    age = (time.time() if now is None else now) - issued
    return 0 <= age <= settings.session_days * 86_400


class LoginThrottle:
    """Allows at most MAX_FAILURES wrong passwords per FAILURE_WINDOW_S (single user: global)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._failures: deque[float] = deque()

    def _prune(self) -> None:
        cutoff = self._clock() - FAILURE_WINDOW_S
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()

    def blocked(self) -> bool:
        self._prune()
        return len(self._failures) >= MAX_FAILURES

    def record_failure(self) -> None:
        self._failures.append(self._clock())

    def reset(self) -> None:
        self._failures.clear()


class LoginRequiredMiddleware:
    """Rejects /api requests without a valid session cookie (401).

    Plain ASGI rather than BaseHTTPMiddleware so streamed (SSE) responses pass untouched.
    Non-API paths (the built UI) stay public: they contain no data, and the UI shows the
    login form when the API answers 401.
    """

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and _protected(scope["path"]):
            token = HTTPConnection(scope).cookies.get(COOKIE_NAME)
            if not token_valid(self.settings, token):
                response = JSONResponse({"detail": "Login required"}, status_code=401)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _protected(path: str) -> bool:
    return (path == "/api" or path.startswith("/api/")) and path not in PUBLIC_PATHS

"""Web UI login (APP_PASSWORD): /api/session. Not to be confused with /api/auth (Google)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from fitbit_app.config import Settings
from fitbit_app.login import (
    COOKIE_NAME,
    LoginThrottle,
    issue_token,
    password_matches,
    token_valid,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["session"])


class SessionStatus(BaseModel):
    required: bool
    authenticated: bool


class LoginRequest(BaseModel):
    password: str


@router.get("/session", response_model=SessionStatus)
async def session_status(request: Request) -> SessionStatus:
    settings: Settings = request.app.state.settings
    if not settings.login_required:
        return SessionStatus(required=False, authenticated=True)
    token = request.cookies.get(COOKIE_NAME)
    return SessionStatus(required=True, authenticated=token_valid(settings, token))


@router.post("/session/login", status_code=status.HTTP_204_NO_CONTENT)
async def login(body: LoginRequest, request: Request, response: Response) -> None:
    settings: Settings = request.app.state.settings
    if not settings.login_required:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Login is not enabled (APP_PASSWORD)")
    throttle: LoginThrottle = request.app.state.login_throttle
    if throttle.blocked():
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many wrong passwords. Wait a minute."
        )
    if not password_matches(settings, body.password):
        throttle.record_failure()
        logger.warning("Failed login attempt")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong password")

    throttle.reset()
    response.set_cookie(
        COOKIE_NAME,
        issue_token(settings),
        max_age=settings.session_days * 86_400,
        httponly=True,
        # Lax (not Strict): the cookie must ride along on Google's redirect back to
        # /api/auth/callback. Cross-site POSTs still don't get it.
        samesite="lax",
        path="/",
    )
    logger.info("Logged in")


@router.post("/session/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax")

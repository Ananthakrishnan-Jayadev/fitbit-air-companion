"""Application exception hierarchy. Caught and logged at boundaries (API, CLI, scheduler)."""


class FitbitAppError(Exception):
    """Base class for all application errors."""


class ConfigError(FitbitAppError):
    """Missing or invalid configuration, or a missing local prerequisite."""


class NotConnectedError(FitbitAppError):
    """No Google account is connected yet."""


class ReauthRequiredError(FitbitAppError):
    """Stored Google credentials are no longer valid; the user must reconnect."""


class OAuthError(FitbitAppError):
    """The OAuth flow failed (bad state, code exchange error, ...)."""


class GoogleApiError(FitbitAppError):
    """A Google Health API request failed. Never carries response bodies with health data."""

    def __init__(self, status_code: int, reason: str, message: str) -> None:
        super().__init__(f"Google Health API error {status_code} ({reason}): {message}")
        self.status_code = status_code
        self.reason = reason

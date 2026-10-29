"""Application exception hierarchy. Caught and logged at boundaries (API, CLI, scheduler)."""


class FitbitAppError(Exception):
    """Base class for all application errors."""


class ConfigError(FitbitAppError):
    """Missing or invalid configuration, or a missing local prerequisite."""

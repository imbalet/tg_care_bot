class BackendClientError(Exception):
    """Base backend client error."""


class BackendUnavailableError(BackendClientError):
    """Backend did not return a usable response."""


class BackendNotFoundError(BackendClientError):
    """Backend resource was not found."""


class BackendUnauthorizedError(BackendClientError):
    """Backend rejected the service credentials."""


class BackendValidationError(BackendClientError):
    """Backend rejected user-provided data."""


__all__ = [
    "BackendClientError",
    "BackendNotFoundError",
    "BackendUnauthorizedError",
    "BackendUnavailableError",
    "BackendValidationError",
]

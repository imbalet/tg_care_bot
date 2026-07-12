class BackendClientError(Exception):
    """Base backend client error."""


class BackendUnavailableError(BackendClientError):
    """Backend did not return a usable response."""


class BackendUnauthorizedError(BackendClientError):
    """Backend rejected the service credentials."""


__all__ = [
    "BackendClientError",
    "BackendUnauthorizedError",
    "BackendUnavailableError",
]

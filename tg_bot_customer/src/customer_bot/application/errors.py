class BackendClientError(Exception):
    """Base backend client error."""


class BackendUnavailableError(BackendClientError):
    """Backend did not return a usable response."""


class BackendUnauthorizedError(BackendClientError):
    """Backend rejected the service credentials."""


class BackendNotFoundError(BackendClientError):
    """Backend did not find requested resource."""


class BackendValidationError(BackendClientError):
    """Backend rejected user-provided data."""


class BackendConflictError(BackendClientError):
    """Backend rejected an operation because of the current resource state."""

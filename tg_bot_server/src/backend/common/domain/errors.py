class AppError(Exception):
    """Base class for expected application errors."""

    message = "Application error"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message or self.message)
        self.details = details or {}


class AuthenticationError(AppError):
    message = "Authentication failed"


class AuthorizationError(AppError):
    message = "Action is not allowed"


class ConflictError(AppError):
    message = "Resource conflict"


class NotFoundError(AppError):
    message = "Resource not found"


class ValidationError(AppError):
    message = "Validation failed"

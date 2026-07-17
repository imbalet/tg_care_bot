from typing import cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.common.domain import (
    AppError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)

ERROR_STATUSES = {
    AuthenticationError: 401,
    AuthorizationError: 403,
    NotFoundError: 404,
    ConflictError: 409,
    ValidationError: 422,
}


def app_error_status(error: AppError) -> int:
    for error_type, status_code in ERROR_STATUSES.items():
        if isinstance(error, error_type):
            return status_code
    return 400


async def app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    app_error = cast(AppError, exc)
    return JSONResponse(
        status_code=app_error_status(app_error),
        content={
            "error": {
                "code": app_error.__class__.__name__,
                "message": str(app_error),
            },
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)

from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.responses import Response

from backend.modules.admin.presentation.surface import admin_csrf_middleware


def register_middlewares(app: FastAPI) -> None:
    @app.middleware("http")
    async def check_admin_csrf(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        return await admin_csrf_middleware(request, call_next)

    @app.middleware("http")
    async def bind_request_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

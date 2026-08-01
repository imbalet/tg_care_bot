from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.responses import Response


def register_middlewares(app: FastAPI) -> None:
    @app.middleware("http")
    async def check_admin_csrf(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and request.url.path.startswith("/admin")
            and request.url.path != "/admin/login"
            and request.headers.get("X-CSRF-Token") is None
        ):
            return Response("CSRF check failed", status_code=403)
        return await call_next(request)

    @app.middleware("http")
    async def bind_request_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

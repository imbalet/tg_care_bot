from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import uuid4

import structlog
from fastapi import Depends, FastAPI, Request
from sqlalchemy import text
from starlette.responses import Response

from backend.bootstrap.container import Container, create_container
from backend.bootstrap.dependencies import get_container
from backend.bootstrap.settings import get_settings
from backend.common.infrastructure.logging import configure_logging
from backend.common.presentation import register_error_handlers, require_service_key
from backend.modules.admin.presentation.api import router as admin_router
from backend.modules.admin.presentation.surface import (
    admin_csrf_middleware,
    create_admin_surface,
)
from backend.modules.catalog.presentation.api import (
    legal_router,
)
from backend.modules.catalog.presentation.api import (
    router as catalog_router,
)
from backend.modules.customers.presentation.api import router as customers_router
from backend.modules.geo.presentation.api import router as geo_router
from backend.modules.performers.presentation.api import (
    admin_router as admin_performers_router,
)
from backend.modules.performers.presentation.api import router as performers_router
from backend.modules.system_checks.presentation.api import (
    router as system_checks_router,
)
from backend.modules.telegram_topics.presentation.api import (
    router as telegram_topics_router,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    container = create_container(settings)
    app.state.container = container
    if not getattr(app.state, "admin_surface_mounted", False):
        create_admin_surface(container).mount_to(app)
        app.state.admin_surface_mounted = True
    try:
        yield
    finally:
        await container.close()


def create_app() -> FastAPI:
    app = FastAPI(title="We Are Close API", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(admin_router)
    app.include_router(catalog_router)
    app.include_router(legal_router)
    app.include_router(customers_router)
    app.include_router(geo_router)
    app.include_router(performers_router)
    app.include_router(admin_performers_router)
    app.include_router(telegram_topics_router)
    app.include_router(system_checks_router)

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
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready(
        container: Annotated[Container, Depends(get_container)],
    ) -> dict[str, str | dict[str, str]]:
        dependencies: dict[str, str] = {}
        async with container.session_factory() as session:
            await session.execute(text("select 1"))
            dependencies["postgres"] = "ok"
        await container.redis.ping()
        dependencies["redis"] = "ok"
        return {"status": "ok", "dependencies": dependencies}

    @app.get("/internal/ping", dependencies=[Depends(require_service_key)])
    async def internal_ping() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

__all__ = ["app", "create_app", "get_container"]

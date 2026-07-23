from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from backend.bootstrap.container import Container, create_container
from backend.bootstrap.middlewares import register_middlewares
from backend.bootstrap.routes import router as bootstrap_router
from backend.bootstrap.settings import Settings, get_settings
from backend.common.infrastructure.logging import configure_logging
from backend.common.presentation import register_error_handlers
from backend.modules.admin.presentation.api.routes import router as admin_router
from backend.modules.admin.presentation.surface import create_admin_surface
from backend.modules.availability.presentation.api import (
    router as availability_router,
)
from backend.modules.catalog.presentation.api import (
    legal_router,
)
from backend.modules.catalog.presentation.api import (
    router as catalog_router,
)
from backend.modules.customers.presentation.api import router as customers_router
from backend.modules.geo.presentation.api import router as geo_router
from backend.modules.orders.presentation.api import router as orders_router
from backend.modules.payments.presentation.api import router as payments_router
from backend.modules.performers.presentation.api import (
    admin_router as admin_performers_router,
)
from backend.modules.performers.presentation.api import router as performers_router
from backend.modules.support.presentation.api import (
    admin_router as admin_support_router,
)
from backend.modules.support.presentation.api import (
    customer_router as customer_support_router,
)
from backend.modules.support.presentation.api import (
    performer_router as performer_support_router,
)
from backend.modules.system_checks.presentation.api import (
    router as system_checks_router,
)

ContainerFactory = Callable[[Settings], Container]
SettingsFactory = Callable[[], Settings]


def _create_lifespan(
    container_factory: ContainerFactory,
    settings_factory: SettingsFactory,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings = settings_factory()
        configure_logging(settings.log_level)
        container = container_factory(settings)
        app.state.container = container
        if not getattr(app.state, "admin_surface_mounted", False):
            create_admin_surface(container).mount_to(app)
            app.state.admin_surface_mounted = True
        try:
            yield
        finally:
            await container.close()

    return lifespan


def create_app(
    *,
    container_factory: ContainerFactory = create_container,
    settings_factory: SettingsFactory = get_settings,
) -> FastAPI:
    app = FastAPI(
        title="We Are Close API",
        lifespan=_create_lifespan(container_factory, settings_factory),
    )
    register_error_handlers(app)
    app.include_router(admin_router)
    app.include_router(availability_router)
    app.include_router(catalog_router)
    app.include_router(legal_router)
    app.include_router(customers_router)
    app.include_router(geo_router)
    app.include_router(orders_router)
    app.include_router(payments_router)
    app.include_router(performers_router)
    app.include_router(admin_performers_router)
    app.include_router(system_checks_router)
    app.include_router(customer_support_router)
    app.include_router(performer_support_router)
    app.include_router(admin_support_router)
    app.include_router(bootstrap_router)

    register_middlewares(app)
    return app


app = create_app()

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from starlette.responses import Response
from starlette_admin import action
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.contrib.sqla import Admin, ModelView
from starlette_admin.exceptions import LoginFailed

from backend.bootstrap.container import Container
from backend.common.domain import AuthenticationError, AuthorizationError
from backend.modules.admin.application import (
    GetCurrentAdminUseCase,
    LoginAdminCommand,
    LoginAdminUseCase,
    LogoutAdminUseCase,
)
from backend.modules.admin.infrastructure import (
    Argon2PasswordHasher,
    RedisAdminSessionStore,
    SqlAlchemyAdminRepository,
)
from backend.modules.admin.presentation.api.routes import ADMIN_SESSION_COOKIE
from backend.modules.catalog.application import SeedMvpCatalogUseCase
from backend.modules.catalog.infrastructure import (
    BusinessSettingModel,
    CityModel,
    DistrictModel,
    LegalDocumentModel,
    ObjectCountMultiplierModel,
    ServiceCategoryModel,
    ServiceModel,
    ServiceOptionModel,
)


class AdminSurfaceAuthProvider(AuthProvider):
    def __init__(self, container: Container) -> None:
        super().__init__()
        self._container = container

    async def is_authenticated(self, request: Request) -> bool:
        session_id = request.cookies.get(ADMIN_SESSION_COOKIE)
        if session_id is None:
            return False
        async with self._container.session_factory() as session:
            use_case = GetCurrentAdminUseCase(
                repository=SqlAlchemyAdminRepository(session),
                session_store=self._session_store(),
            )
            try:
                admin, _csrf_token = await use_case.execute(session_id)
            except AuthenticationError, AuthorizationError:
                return False
        request.state.admin_user = admin
        return True

    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response,
    ) -> Response:
        async with self._container.session_factory() as session:
            use_case = LoginAdminUseCase(
                repository=SqlAlchemyAdminRepository(session),
                password_hasher=Argon2PasswordHasher(),
                session_store=self._session_store(),
            )
            try:
                result = await use_case.execute(
                    LoginAdminCommand(email=username, password=password),
                )
            except (AuthenticationError, AuthorizationError) as exc:
                raise LoginFailed("Invalid email or password") from exc
            await session.commit()
        response.set_cookie(
            key=ADMIN_SESSION_COOKIE,
            value=result.session_id,
            max_age=self._container.settings.admin_session_ttl_seconds,
            httponly=True,
            secure=self._container.settings.environment == "production",
            samesite="strict",
            path="/admin",
        )
        return response

    async def logout(self, request: Request, response: Response) -> Response:
        session_id = request.cookies.get(ADMIN_SESSION_COOKIE)
        if session_id is not None:
            await LogoutAdminUseCase(self._session_store()).execute(session_id)
        response.delete_cookie(ADMIN_SESSION_COOKIE, path="/admin")
        return response

    def get_admin_user(self, request: Request) -> AdminUser | None:
        admin = getattr(request.state, "admin_user", None)
        if admin is None:
            return None
        return AdminUser(username=admin.email)

    def _session_store(self) -> RedisAdminSessionStore:
        return RedisAdminSessionStore(
            redis=self._container.redis,
            ttl_seconds=self._container.settings.admin_session_ttl_seconds,
        )


class CatalogModelView(ModelView):
    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    def can_delete(self, request: Request) -> bool:
        return False

    def is_accessible(self, request: Request) -> bool:
        return getattr(request.state, "admin_user", None) is not None


class LegalDocumentView(CatalogModelView):
    exclude_fields_from_edit = ["id", "created_at"]
    exclude_fields_from_create = ["id", "created_at"]


class BusinessSettingView(CatalogModelView):
    actions = ["seed_mvp_catalog"]

    @action(
        name="seed_mvp_catalog",
        text="Seed MVP catalog",
        confirmation="Run idempotent MVP catalog seed?",
        submit_btn_text="Seed",
    )
    async def seed_mvp_catalog_action(
        self,
        request: Request,
        _pks: list[Any],
    ) -> str:
        await SeedMvpCatalogUseCase(request.state.session).execute()
        return "MVP catalog seed completed"


def create_admin_surface(container: Container) -> Admin:
    admin = Admin(
        engine=container.engine,
        title="We Are Close Admin",
        base_url="/admin/catalog",
        route_name="admin_catalog",
        auth_provider=AdminSurfaceAuthProvider(container),
    )
    admin.add_view(CatalogModelView(CityModel, label="Cities"))
    admin.add_view(CatalogModelView(DistrictModel, label="Districts"))
    admin.add_view(CatalogModelView(ServiceCategoryModel, label="Service categories"))
    admin.add_view(CatalogModelView(ServiceModel, label="Services"))
    admin.add_view(CatalogModelView(ServiceOptionModel, label="Service options"))
    admin.add_view(
        CatalogModelView(ObjectCountMultiplierModel, label="Object count multipliers"),
    )
    admin.add_view(BusinessSettingView(BusinessSettingModel, label="Business settings"))
    admin.add_view(LegalDocumentView(LegalDocumentModel, label="Legal documents"))
    return admin


async def admin_csrf_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if _requires_admin_csrf_header_check(request):
        return Response("CSRF check failed", status_code=403)
    return await call_next(request)


def _requires_admin_csrf_header_check(request: Request) -> bool:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return False
    if not request.url.path.startswith("/admin"):
        return False
    if request.url.path in {"/admin/login", "/admin/catalog/login"}:
        return False
    if request.headers.get("X-CSRF-Token"):
        return False
    sec_fetch_site = request.headers.get("Sec-Fetch-Site")
    if sec_fetch_site in {"same-origin", "same-site", "none"}:
        return False
    if sec_fetch_site == "cross-site":
        return True
    origin = request.headers.get("Origin")
    if origin is not None:
        return origin != _request_origin(request)
    referer = request.headers.get("Referer")
    if referer is not None:
        return not referer.startswith(_request_origin(request))
    return True


def _request_origin(request: Request) -> str:
    return f"{request.url.scheme}://{request.headers['host']}"


__all__ = [
    "AdminSurfaceAuthProvider",
    "admin_csrf_middleware",
    "create_admin_surface",
]

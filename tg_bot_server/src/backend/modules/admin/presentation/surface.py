from collections.abc import Awaitable, Callable
from typing import Any, cast
from uuid import UUID

from fastapi import Request
from starlette.responses import Response
from starlette_admin import action
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.contrib.sqla import Admin, ModelView
from starlette_admin.exceptions import FormValidationError, LoginFailed

from backend.bootstrap.container import Container
from backend.common.domain import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from backend.modules.addresses.infrastructure import AddressModel
from backend.modules.admin.application import (
    LoginAdminCommand,
)
from backend.modules.admin.infrastructure import (
    AdminAuditLogModel,
)
from backend.modules.admin.presentation.api.routes import ADMIN_SESSION_COOKIE
from backend.modules.care_objects.infrastructure import CareObjectModel
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
from backend.modules.customers.infrastructure import CustomerModel
from backend.modules.files.infrastructure import (
    FileLinkModel,
    FileModel,
    SqlAlchemyFileRepository,
)
from backend.modules.orders.infrastructure import (
    OrderCareObjectModel,
    OrderMatchModel,
    OrderModel,
    OrderOptionValueModel,
    OrderStatusHistoryModel,
)
from backend.modules.payments.infrastructure import PaymentModel, RefundModel
from backend.modules.performers.application import CreateInvitationCommand
from backend.modules.performers.infrastructure import (
    PerformerCalendarOverrideModel,
    PerformerInvitationModel,
    PerformerModel,
    PerformerScheduleModel,
    PerformerServiceModel,
)


class AdminSurfaceAuthProvider(AuthProvider):
    def __init__(self, container: Container) -> None:
        super().__init__()
        self._container = container

    async def is_authenticated(self, request: Request) -> bool:
        session_id = request.cookies.get(ADMIN_SESSION_COOKIE)
        if session_id is None:
            return False
        try:
            admin, _csrf_token = await self._container.services().get_current_admin(
                session_id,
            )
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
        try:
            result = await self._container.services().login_admin(
                LoginAdminCommand(email=username, password=password),
            )
        except (AuthenticationError, AuthorizationError) as exc:
            raise LoginFailed("Invalid email or password") from exc
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
            await self._container.services().logout_admin(session_id)
        response.delete_cookie(ADMIN_SESSION_COOKIE, path="/admin")
        return response

    def get_admin_user(self, request: Request) -> AdminUser | None:
        admin = getattr(request.state, "admin_user", None)
        if admin is None:
            return None
        return AdminUser(username=admin.email)


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


class ReadOnlyModelView(ModelView):
    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    def is_accessible(self, request: Request) -> bool:
        return getattr(request.state, "admin_user", None) is not None


class UseCaseManagedModelView(ReadOnlyModelView):
    """Admin mutations for this model must go through application use cases."""


class PerformerView(ReadOnlyModelView):
    actions = ["activate_performer"]

    def __init__(self, model: type[Any], container: Container, **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self._container = container

    @action(
        name="activate_performer",
        text="Activate performer",
        confirmation="Activate selected performers?",
        submit_btn_text="Activate",
    )
    async def activate_performer_action(self, request: Request, pks: list[Any]) -> str:
        admin = getattr(request.state, "admin_user", None)
        if admin is None:
            raise FormValidationError({"id": "Admin session is required"})
        activated_count = 0
        errors: dict[str | int, Any] = {}
        for raw_pk in pks:
            performer_id = UUID(str(raw_pk))
            try:
                await self._container.services().activate_performer(
                    performer_id,
                    audit_admin_id=admin.id,
                )
            except NotFoundError as exc:
                errors[str(raw_pk)] = str(exc)
            else:
                activated_count += 1
        if errors:
            raise FormValidationError(errors)
        return f"Activated performers: {activated_count}"


class PerformerInvitationView(ReadOnlyModelView):
    exclude_fields_from_create = [
        "id",
        "created_by_admin_id",
        "status",
        "accepted_performer_id",
        "created_at",
        "updated_at",
    ]

    def __init__(self, model: type[Any], container: Container, **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self._container = container

    def can_create(self, request: Request) -> bool:
        return self.is_accessible(request)

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        errors: dict[str | int, Any] = {}
        telegram_id = data.get("telegram_id")
        if not isinstance(telegram_id, int) or telegram_id <= 0:
            errors["telegram_id"] = "Telegram ID must be a positive integer"
        if errors:
            raise FormValidationError(errors)

    async def create(
        self,
        request: Request,
        data: dict[str, Any],
    ) -> PerformerInvitationModel:
        await self.validate(request, data)
        admin = getattr(request.state, "admin_user", None)
        if admin is None:
            raise FormValidationError({"telegram_id": "Admin session is required"})
        try:
            invitation = await self._container.services().create_invitation(
                CreateInvitationCommand(
                    telegram_id=data["telegram_id"],
                    created_by_admin_id=admin.id,
                    expires_at=data.get("expires_at"),
                ),
                audit_admin_id=admin.id,
            )
        except (ConflictError, ValidationError) as exc:
            raise FormValidationError({"telegram_id": str(exc)}) from exc
        model = await request.state.session.get(PerformerInvitationModel, invitation.id)
        if model is None:
            raise FormValidationError({"telegram_id": "Invitation was not created"})
        return cast(PerformerInvitationModel, model)


class FileReviewView(ReadOnlyModelView):
    actions = ["hide_file"]

    @action(
        name="hide_file",
        text="Hide file",
        confirmation="Hide selected files from active use?",
        submit_btn_text="Hide",
    )
    async def hide_file_action(self, request: Request, pks: list[Any]) -> str:
        repository = SqlAlchemyFileRepository(request.state.session)
        admin = getattr(request.state, "admin_user", None)
        hidden_count = 0
        for raw_pk in pks:
            file_id = UUID(str(raw_pk))
            await repository.mark_deleted(file_id)
            request.state.session.add(
                AdminAuditLogModel(
                    admin_id=admin.id if admin is not None else None,
                    action="hide_file",
                    entity_type="file",
                    entity_id=file_id,
                    reason=None,
                    audit_metadata={},
                ),
            )
            hidden_count += 1
        return f"Hidden files: {hidden_count}"


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
    admin.add_view(ReadOnlyModelView(BusinessSettingModel, label="Business settings"))
    admin.add_view(LegalDocumentView(LegalDocumentModel, label="Legal documents"))
    admin.add_view(ReadOnlyModelView(CustomerModel, label="Customers"))
    admin.add_view(PerformerView(PerformerModel, container, label="Performers"))
    admin.add_view(
        PerformerInvitationView(
            PerformerInvitationModel,
            container,
            label="Performer invitations",
        ),
    )
    admin.add_view(
        UseCaseManagedModelView(PerformerServiceModel, label="Performer services")
    )
    admin.add_view(
        ReadOnlyModelView(PerformerScheduleModel, label="Performer schedules"),
    )
    admin.add_view(
        ReadOnlyModelView(
            PerformerCalendarOverrideModel,
            label="Performer calendar overrides",
        ),
    )
    admin.add_view(ReadOnlyModelView(OrderModel, label="Orders"))
    admin.add_view(ReadOnlyModelView(OrderMatchModel, label="Order matches"))
    admin.add_view(ReadOnlyModelView(OrderCareObjectModel, label="Order care objects"))
    admin.add_view(
        ReadOnlyModelView(OrderOptionValueModel, label="Order option values")
    )
    admin.add_view(
        ReadOnlyModelView(OrderStatusHistoryModel, label="Order status history"),
    )
    admin.add_view(ReadOnlyModelView(PaymentModel, label="Payments"))
    admin.add_view(ReadOnlyModelView(RefundModel, label="Refunds"))
    admin.add_view(ReadOnlyModelView(CareObjectModel, label="Care objects"))
    admin.add_view(ReadOnlyModelView(AddressModel, label="Addresses"))
    admin.add_view(FileReviewView(FileModel, label="Files"))
    admin.add_view(ReadOnlyModelView(FileLinkModel, label="File links"))
    admin.add_view(ReadOnlyModelView(AdminAuditLogModel, label="Admin audit"))
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

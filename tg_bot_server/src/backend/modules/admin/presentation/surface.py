import json
from collections.abc import Awaitable, Callable
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from uuid import UUID

from fastapi import Request
from sqlalchemy import select
from starlette.responses import Response
from starlette_admin import action
from starlette_admin._types import RequestAction
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.contrib.sqla import Admin, ModelView
from starlette_admin.exceptions import FormValidationError, LoginFailed
from starlette_admin.fields import JSONField

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
    OrderAddressSnapshotModel,
    OrderCareObjectModel,
    OrderMatchModel,
    OrderModel,
    OrderOptionValueModel,
    OrderReportModel,
    OrderStatusHistoryModel,
)
from backend.modules.payments.application import CreateManualRefundCommand
from backend.modules.payments.infrastructure import PaymentModel, RefundModel
from backend.modules.performers.application import CreateInvitationCommand
from backend.modules.performers.infrastructure import (
    PerformerCalendarOverrideModel,
    PerformerInvitationModel,
    PerformerModel,
    PerformerScheduleModel,
    PerformerServiceModel,
)
from backend.modules.support.infrastructure import (
    AccountDeletionRequestModel,
    ComplaintModel,
    SupportRequestModel,
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
            admin, _csrf_token = await self._container.admin.get_current_admin(
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
            result = await self._container.admin.login_admin(
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
            await self._container.admin.logout_admin(session_id)
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
    page_size = 25

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


class OperationalModelView(ReadOnlyModelView):
    search_builder = True


class PaymentView(OperationalModelView):
    actions = ["create_manual_refund"]
    exclude_fields_from_list = ["confirmation_url", "idempotency_key"]
    exclude_fields_from_detail = ["confirmation_url", "idempotency_key"]
    searchable_fields = [
        "id",
        "order_id",
        "provider",
        "status",
        "provider_payment_id",
        "amount",
        "created_at",
        "paid_at",
        "expires_at",
    ]
    sortable_fields = ["created_at", "expires_at", "paid_at", "amount", "status"]

    def __init__(self, model: type[Any], container: Container, **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self._container = container

    @action(
        name="create_manual_refund",
        text="Create manual refund",
        confirmation="Create a refund for selected payments?",
        submit_btn_text="Refund",
        form=(
            '<input name="amount" placeholder="Full amount by default">'
            '<textarea name="reason" required></textarea>'
        ),
    )
    async def create_manual_refund_action(
        self, request: Request, pks: list[Any]
    ) -> str:
        admin = getattr(request.state, "admin_user", None)
        if admin is None:
            raise FormValidationError({"id": "Admin session is required"})
        data = await request.form()
        raw_amount = str(data.get("amount", "")).strip()
        reason = str(data.get("reason", "")).strip()
        if not reason:
            raise FormValidationError({"reason": "Reason is required"})
        amount: Decimal | None = None
        if raw_amount:
            try:
                amount = Decimal(raw_amount)
            except InvalidOperation as exc:
                raise FormValidationError({"amount": "Invalid amount"}) from exc
        for raw_pk in pks:
            try:
                await self._container.payments.create_manual_refund(
                    CreateManualRefundCommand(
                        payment_id=UUID(str(raw_pk)),
                        amount=amount,
                        reason=reason,
                        admin_id=admin.id,
                    ),
                )
            except (ConflictError, NotFoundError, ValidationError) as exc:
                raise FormValidationError({str(raw_pk): str(exc)}) from exc
        return f"Refunds created: {len(pks)}"


class AuditLogView(OperationalModelView):
    searchable_fields = ["admin_id", "action", "entity_type", "entity_id"]
    sortable_fields = ["created_at", "action", "entity_type"]


class RefundView(OperationalModelView):
    searchable_fields = [
        "id",
        "order_id",
        "payment_id",
        "status",
        "amount",
        "created_at",
        "completed_at",
    ]
    sortable_fields = ["created_at", "completed_at", "amount", "status"]


class ReportView(OperationalModelView):
    searchable_fields = [
        "id",
        "order_id",
        "performer_id",
        "problem_flag",
        "submitted_at",
    ]
    sortable_fields = ["submitted_at", "problem_flag"]

    def __init__(self, model: type[Any], container: Container, **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self._container = container
        self.fields = [*self.fields, JSONField("report_photo_urls", read_only=True)]

    async def serialize(
        self,
        obj: Any,
        request: Request,
        action: RequestAction,
        include_relationships: bool = True,
        include_select2: bool = False,
    ) -> dict[str, Any]:
        if action == RequestAction.DETAIL:
            result = await request.state.session.execute(
                select(FileModel)
                .join(FileLinkModel, FileLinkModel.file_id == FileModel.id)
                .where(
                    FileLinkModel.entity_type == "order_report",
                    FileLinkModel.entity_id == obj.id,
                    FileLinkModel.purpose == "report_photo",
                    FileModel.status == "uploaded",
                    FileModel.storage_key.is_not(None),
                )
                .order_by(FileLinkModel.sort_order),
            )
            obj.report_photo_urls = [
                await self._container.storage.create_download_url(
                    file.storage_key,
                )
                for file in result.scalars()
                if file.storage_key is not None
            ]
        return await super().serialize(
            obj,
            request,
            action,
            include_relationships=include_relationships,
            include_select2=include_select2,
        )


class BusinessSettingView(OperationalModelView):
    actions = ["update_business_setting"]

    @action(
        name="update_business_setting",
        text="Update setting",
        confirmation="Update selected business settings?",
        submit_btn_text="Save",
        form='<textarea name="value" required></textarea>',
    )
    async def update_business_setting_action(
        self, request: Request, pks: list[Any]
    ) -> str:
        admin = getattr(request.state, "admin_user", None)
        if admin is None:
            raise FormValidationError({"id": "Admin session is required"})
        data = await request.form()
        raw_value = str(data.get("value", ""))
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise FormValidationError({"value": "Value must be valid JSON"}) from exc
        for raw_pk in pks:
            setting = await request.state.session.get(
                BusinessSettingModel, UUID(str(raw_pk))
            )
            if setting is None:
                raise FormValidationError({str(raw_pk): "Setting not found"})
            try:
                await self._container.admin.update_business_setting(
                    key=setting.key, value=value, admin_id=admin.id
                )
            except (NotFoundError, ValidationError) as exc:
                raise FormValidationError({"value": str(exc)}) from exc
        return f"Updated settings: {len(pks)}"

    def __init__(self, model: type[Any], container: Container, **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self._container = container


class PerformerView(ReadOnlyModelView):
    actions = ["activate_performer", "reject_performer"]
    searchable_fields = ["id", "telegram_id", "full_name", "status", "city_id"]
    sortable_fields = ["created_at", "updated_at", "status"]

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
                await self._container.performers.activate_performer(
                    performer_id,
                    audit_admin_id=admin.id,
                )
            except (ConflictError, NotFoundError) as exc:
                errors[str(raw_pk)] = str(exc)
            else:
                activated_count += 1
        if errors:
            raise FormValidationError(errors)
        return f"Activated performers: {activated_count}"

    @action(
        name="reject_performer",
        text="Reject performer",
        confirmation="Reject selected performers?",
        submit_btn_text="Reject",
        form=(
            '<input name="reason" required maxlength="200">'
            '<textarea name="comment" required></textarea>'
        ),
    )
    async def reject_performer_action(self, request: Request, pks: list[Any]) -> str:
        admin = getattr(request.state, "admin_user", None)
        if admin is None:
            raise FormValidationError({"id": "Admin session is required"})
        data = await request.form()
        reason = str(data.get("reason", "")).strip()
        comment = str(data.get("comment", "")).strip()
        if not reason or not comment:
            raise FormValidationError({"reason": "Reason and comment are required"})
        for raw_pk in pks:
            try:
                await self._container.performers.reject_performer(
                    performer_id=UUID(str(raw_pk)),
                    reason=reason,
                    comment=comment,
                    admin_id=admin.id,
                )
            except (ConflictError, NotFoundError) as exc:
                raise FormValidationError({str(raw_pk): str(exc)}) from exc
        return f"Rejected performers: {len(pks)}"


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
            invitation = await self._container.performers.create_invitation(
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


class OrderView(OperationalModelView):
    actions = ["cancel_order", "force_close_order"]
    searchable_fields = [
        "id",
        "customer_id",
        "selected_performer_id",
        "status",
        "service_code",
        "created_at",
        "start_at",
        "end_at",
    ]
    sortable_fields = ["created_at", "start_at", "end_at", "status", "total_amount"]

    def __init__(self, model: type[Any], container: Container, **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self._container = container
        self.fields = [
            *self.fields,
            JSONField("customer_contact", read_only=True),
            JSONField("address_snapshot", read_only=True),
        ]

    async def serialize(
        self,
        obj: Any,
        request: Request,
        action: RequestAction,
        include_relationships: bool = True,
        include_select2: bool = False,
    ) -> dict[str, Any]:
        if action == RequestAction.DETAIL:
            customer = (
                await request.state.session.get(CustomerModel, obj.customer_id)
                if obj.customer_id is not None
                else None
            )
            snapshot = await request.state.session.scalar(
                select(OrderAddressSnapshotModel).where(
                    OrderAddressSnapshotModel.order_id == obj.id,
                ),
            )
            obj.customer_contact = (
                {
                    "phone": customer.phone,
                    "telegram_username": customer.telegram_username,
                }
                if customer is not None
                else None
            )
            obj.address_snapshot = (
                {
                    "city_name": snapshot.city_name,
                    "district_name": snapshot.district_name,
                    "address_text": snapshot.address_text,
                    "entrance": snapshot.entrance,
                    "floor": snapshot.floor,
                    "apartment": snapshot.apartment,
                    "comment": snapshot.comment,
                }
                if snapshot is not None
                else None
            )
        return await super().serialize(
            obj,
            request,
            action,
            include_relationships=include_relationships,
            include_select2=include_select2,
        )

    @action(
        name="cancel_order",
        text="Cancel order",
        confirmation="Cancel selected orders?",
        submit_btn_text="Cancel",
        form='<textarea name="comment" required></textarea>',
    )
    async def cancel_order_action(self, request: Request, pks: list[Any]) -> str:
        return await self._close_orders(request, pks, force=False)

    @action(
        name="force_close_order",
        text="Force close order",
        confirmation="Force close selected non-terminal orders?",
        submit_btn_text="Force close",
        form='<textarea name="comment" required></textarea>',
    )
    async def force_close_order_action(self, request: Request, pks: list[Any]) -> str:
        return await self._close_orders(request, pks, force=True)

    async def _close_orders(
        self, request: Request, pks: list[Any], *, force: bool
    ) -> str:
        admin = getattr(request.state, "admin_user", None)
        if admin is None:
            raise FormValidationError({"id": "Admin session is required"})
        comment = str((await request.form()).get("comment", "")).strip()
        if not comment:
            raise FormValidationError({"comment": "Comment is required"})
        closed = 0
        for raw_pk in pks:
            order = await request.state.session.get(OrderModel, UUID(str(raw_pk)))
            if order is None:
                raise FormValidationError({str(raw_pk): "Order not found"})
            if force and order.status in {"completed", "cancelled", "expired"}:
                raise FormValidationError({str(raw_pk): "Order is terminal"})
            payment = None
            if order.active_payment_id is not None:
                payment = await request.state.session.get(
                    PaymentModel,
                    order.active_payment_id,
                )
            try:
                await self._container.orders.cancel_order(
                    order_id=order.id,
                    actor_type="admin",
                    actor_id=admin.id,
                    comment=comment,
                )
                if force and payment is not None and payment.status == "succeeded":
                    await self._container.payments.create_manual_refund(
                        CreateManualRefundCommand(
                            payment_id=payment.id,
                            amount=payment.amount,
                            reason=f"admin_force_close: {comment}",
                            admin_id=admin.id,
                        )
                    )
            except (ConflictError, NotFoundError, ValidationError) as exc:
                raise FormValidationError({str(raw_pk): str(exc)}) from exc
            closed += 1
        return f"Closed orders: {closed}"


class SupportRecordView(OperationalModelView):
    searchable_fields = [
        "id",
        "customer_id",
        "performer_id",
        "order_id",
        "status",
        "created_at",
        "updated_at",
    ]
    sortable_fields = ["created_at", "updated_at", "status"]

    def __init__(
        self, model: type[Any], container: Container, record_kind: str, **kwargs: Any
    ) -> None:
        super().__init__(model, **kwargs)
        self._container = container
        self._record_kind = record_kind
        self.actions = ["update_record"]
        if record_kind == "deletion":
            self.actions.append("resolve_deletion")

    @action(
        name="update_record",
        text="Update status",
        confirmation="Update selected records?",
        submit_btn_text="Save",
        form='<input name="status" required><textarea name="comment"></textarea>',
    )
    async def update_record_action(self, request: Request, pks: list[Any]) -> str:
        admin = getattr(request.state, "admin_user", None)
        if admin is None:
            raise FormValidationError({"id": "Admin session is required"})
        data = await request.form()
        status = str(data.get("status", "")).strip()
        comment = str(data.get("comment", "")).strip() or None
        if not status:
            raise FormValidationError({"status": "Status is required"})
        for raw_pk in pks:
            try:
                await self._container.support.update_support_record(
                    record_kind=self._record_kind,
                    record_id=UUID(str(raw_pk)),
                    status=status,
                    admin_comment=comment,
                    admin_id=admin.id,
                )
            except (ConflictError, NotFoundError, ValidationError) as exc:
                raise FormValidationError({str(raw_pk): str(exc)}) from exc
        return f"Updated records: {len(pks)}"

    @action(
        name="resolve_deletion",
        text="Resolve deletion",
        confirmation="Resolve selected deletion requests?",
        submit_btn_text="Resolve",
        form='<textarea name="comment" required></textarea>',
    )
    async def resolve_deletion_action(self, request: Request, pks: list[Any]) -> str:
        admin = getattr(request.state, "admin_user", None)
        if admin is None:
            raise FormValidationError({"id": "Admin session is required"})
        comment = str((await request.form()).get("comment", "")).strip()
        if not comment:
            raise FormValidationError({"comment": "Comment is required"})
        for raw_pk in pks:
            try:
                await self._container.support.resolve_deletion_request(
                    record_id=UUID(str(raw_pk)),
                    admin_comment=comment,
                    admin_id=admin.id,
                )
            except (ConflictError, NotFoundError, ValidationError) as exc:
                raise FormValidationError({str(raw_pk): str(exc)}) from exc
        return f"Deletion requests resolved: {len(pks)}"


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
    admin.add_view(
        BusinessSettingView(
            BusinessSettingModel,
            container,
            label="Business settings",
        ),
    )
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
    admin.add_view(OrderView(OrderModel, container, label="Orders"))
    admin.add_view(OperationalModelView(OrderMatchModel, label="Order matches"))
    admin.add_view(ReadOnlyModelView(OrderCareObjectModel, label="Order care objects"))
    admin.add_view(
        ReadOnlyModelView(OrderOptionValueModel, label="Order option values")
    )
    admin.add_view(
        ReadOnlyModelView(OrderStatusHistoryModel, label="Order status history"),
    )
    admin.add_view(PaymentView(PaymentModel, container, label="Payments"))
    admin.add_view(RefundView(RefundModel, label="Refunds"))
    admin.add_view(ReportView(OrderReportModel, container, label="Order reports"))
    admin.add_view(
        SupportRecordView(
            SupportRequestModel,
            container,
            "support",
            label="Support requests",
        ),
    )
    admin.add_view(
        SupportRecordView(
            ComplaintModel,
            container,
            "complaint",
            label="Complaints",
        ),
    )
    admin.add_view(
        SupportRecordView(
            AccountDeletionRequestModel,
            container,
            "deletion",
            label="Deletion requests",
        ),
    )
    admin.add_view(ReadOnlyModelView(CareObjectModel, label="Care objects"))
    admin.add_view(ReadOnlyModelView(AddressModel, label="Addresses"))
    admin.add_view(FileReviewView(FileModel, label="Files"))
    admin.add_view(ReadOnlyModelView(FileLinkModel, label="File links"))
    admin.add_view(AuditLogView(AdminAuditLogModel, label="Admin audit"))
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

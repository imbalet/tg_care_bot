import secrets
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, Response

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.domain import (
    AuthenticationError,
    AuthorizationError,
    ValidationError,
)
from backend.modules.admin.application import (
    LoginAdminCommand,
)
from backend.modules.payments.application import (
    CreateManualRefundCommand,
    RetryPaymentOperationCommand,
)

from .mappers import admin_response
from .schemas import (
    AdminNotificationPageResponse,
    AdminNotificationResponse,
    AdminResponse,
    BusinessSettingResponse,
    LoginRequest,
    LoginResponse,
    ManualRefundRequest,
    ManualRefundResponse,
    MarkAdminNotificationsReadRequest,
    MarkAdminNotificationsReadResponse,
    PaymentRetryResponse,
    UpdateBusinessSettingRequest,
)

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_SESSION_COOKIE = "admin_session"
CSRF_HEADER = "X-CSRF-Token"


def _cookie_secure(container: Container) -> bool:
    return container.settings.environment == "production"


@router.post("/login")
async def login(
    request: LoginRequest,
    response: Response,
    container: Annotated[Container, Depends(get_container)],
) -> LoginResponse:
    result = await container.admin.login_admin(
        LoginAdminCommand(email=str(request.email), password=request.password),
    )
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=result.session_id,
        max_age=container.settings.admin_session_ttl_seconds,
        httponly=True,
        secure=_cookie_secure(container),
        samesite="lax",
        path="/admin",
    )
    return LoginResponse(
        admin=admin_response(result.admin),
        csrf_token=result.csrf_token,
    )


async def get_current_admin(
    container: Annotated[Container, Depends(get_container)],
    admin_session: Annotated[str | None, Cookie(alias=ADMIN_SESSION_COOKIE)] = None,
) -> tuple[AdminResponse, str, str]:
    if admin_session is None:
        raise AuthenticationError("Admin session is required")
    admin, csrf_token = await container.admin.get_current_admin(admin_session)
    return (
        admin_response(admin),
        csrf_token,
        admin_session,
    )


async def require_admin_csrf(
    current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> tuple[AdminResponse, str, str]:
    expected = current[1]
    if csrf_token is None or not secrets.compare_digest(csrf_token, expected):
        raise AuthorizationError("CSRF token is invalid")
    return current


@router.get("/me")
async def me(
    current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
) -> AdminResponse:
    return current[0]


@router.get("/notifications")
async def list_notifications(
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
    status: str | None = None,
    is_read: bool | None = None,
    page: int = 1,
    page_size: int = 50,
) -> AdminNotificationPageResponse:
    if page < 1 or page_size < 1 or page_size > 100:
        raise ValidationError("Invalid pagination")
    items, total = await container.admin.list_admin_notifications(
        admin_id=UUID(current[0].id),
        status=status,
        is_read=is_read,
        page=page,
        page_size=page_size,
    )
    return AdminNotificationPageResponse(
        items=[
            AdminNotificationResponse(
                id=item.id,
                type=item.type,
                entity_type=item.entity_type,
                entity_id=item.entity_id,
                payload=item.payload,
                status=item.status,
                read_at=item.read_at.isoformat() if item.read_at else None,
                created_at=item.created_at.isoformat(),
                sent_at=item.sent_at.isoformat() if item.sent_at else None,
                last_error=item.last_error,
            )
            for item in items
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/notifications/read", response_model=MarkAdminNotificationsReadResponse)
async def mark_notifications_read(
    request: MarkAdminNotificationsReadRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> MarkAdminNotificationsReadResponse:
    marked = await container.admin.mark_admin_notifications_read(
        admin_id=UUID(current[0].id),
        notification_ids=request.ids,
    )
    return MarkAdminNotificationsReadResponse(marked=marked)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> None:
    session_id = current[2]
    await container.admin.logout_admin(session_id)
    response.delete_cookie(ADMIN_SESSION_COOKIE, path="/admin")


@router.patch("/business-settings/{key}")
async def update_business_setting(
    key: str,
    request: UpdateBusinessSettingRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> BusinessSettingResponse:
    admin_id = UUID(current[0].id)
    return await container.admin.update_business_setting(
        key=key,
        value=request.value,
        admin_id=admin_id,
    )


@router.post("/payments/refunds")
async def create_manual_refund(
    request: ManualRefundRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> ManualRefundResponse:
    admin_id = UUID(current[0].id)
    refund = await container.payments.create_manual_refund(
        CreateManualRefundCommand(
            payment_id=request.payment_id,
            amount=Decimal(request.amount) if request.amount is not None else None,
            reason=request.reason,
            admin_id=admin_id,
        ),
    )
    return ManualRefundResponse(
        id=str(refund.id),
        order_id=str(refund.order_id),
        payment_id=str(refund.payment_id),
        refund_type=refund.refund_type,
        amount=str(refund.amount),
        status=refund.status,
        reason=refund.reason,
        provider_refund_id=refund.provider_refund_id,
    )


@router.post("/payments/{payment_id}/retry-check")
async def retry_payment_operation(
    payment_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> PaymentRetryResponse:
    admin_id = UUID(current[0].id)
    result = await container.payments.retry_payment_operation(
        command=RetryPaymentOperationCommand(payment_id=payment_id),
        admin_id=admin_id,
    )
    return PaymentRetryResponse(
        status=result.status if result is not None else "checked",
        applied=result.applied if result is not None else False,
        unapplied_reason=result.unapplied_reason if result is not None else None,
    )

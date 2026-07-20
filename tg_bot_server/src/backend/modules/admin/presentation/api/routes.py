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
    AdminResponse,
    BusinessSettingResponse,
    LoginRequest,
    LoginResponse,
    ManualRefundRequest,
    ManualRefundResponse,
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
    result = await container.services().login_admin(
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
    admin, csrf_token = await container.services().get_current_admin(admin_session)
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


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> None:
    session_id = current[2]
    await container.services().logout_admin(session_id)
    response.delete_cookie(ADMIN_SESSION_COOKIE, path="/admin")


@router.patch("/business-settings/{key}")
async def update_business_setting(
    key: str,
    request: UpdateBusinessSettingRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> BusinessSettingResponse:
    admin_id = UUID(current[0].id)
    return await container.services().update_business_setting(
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
    refund = await container.services().create_manual_refund(
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
    result = await container.services().retry_payment_operation(
        command=RetryPaymentOperationCommand(payment_id=payment_id),
        admin_id=admin_id,
    )
    return PaymentRetryResponse(
        status=result.status if result is not None else "checked",
        applied=result.applied if result is not None else False,
        unapplied_reason=result.unapplied_reason if result is not None else None,
    )

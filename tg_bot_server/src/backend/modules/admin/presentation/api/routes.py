import secrets
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, Query, Response

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.domain import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from backend.modules.admin.application import (
    LoginAdminCommand,
)
from backend.modules.admin.infrastructure.persistence.query_service import (
    AdminResourceNotFound,
)
from backend.modules.availability.application import (
    AddCalendarOverrideCommand,
    SetPerformerScheduleCommand,
)
from backend.modules.payments.application import (
    CreateManualRefundCommand,
    RetryPaymentOperationCommand,
)
from backend.modules.performers.application import (
    ApprovePerformerServiceCommand,
    CreateInvitationCommand,
)

from .mappers import admin_response
from .schemas import (
    AdminAddPerformerServiceRequest,
    AdminAssignPerformerRequest,
    AdminCatalogCityRequest,
    AdminCatalogResourceUpdateRequest,
    AdminCatalogServiceOptionRequest,
    AdminCatalogServiceRequest,
    AdminCommentRequest,
    AdminInvitationRequest,
    AdminManualPayoutRequest,
    AdminNotificationPageResponse,
    AdminNotificationResponse,
    AdminOrderPerformerActionRequest,
    AdminPayoutDecisionRequest,
    AdminPerformerCalendarOverrideRequest,
    AdminPerformerDecisionRequest,
    AdminPerformerProfileRequest,
    AdminPerformerRejectRequest,
    AdminPerformerScheduleRequest,
    AdminPerformerServiceLimitsRequest,
    AdminPerformerServiceRequest,
    AdminRefundRequest,
    AdminResourceDetailResponse,
    AdminResourcePageResponse,
    AdminResponse,
    AdminSessionResponse,
    AdminSupportUpdateRequest,
    AdminViolationRequest,
    AdminViolationResolveRequest,
    BusinessSettingResponse,
    LoginRequest,
    LoginResponse,
    ManualPayoutRequest,
    ManualPayoutResponse,
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


@router.get("/session")
async def session(
    current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
) -> AdminSessionResponse:
    """Return the authenticated admin and CSRF token for browser clients."""
    return AdminSessionResponse(admin=current[0], csrf_token=current[1])


@router.get("/ui/dashboard")
async def ui_dashboard(
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
) -> dict[str, Any]:
    return await container.admin.get_ui_dashboard(admin_id=UUID(current[0].id))


@router.get("/ui/work-queues/{queue}")
async def ui_work_queue(
    queue: str,
    container: Annotated[Container, Depends(get_container)],
    _current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    try:
        return await container.admin.get_ui_work_queue(queue, limit=limit)
    except AdminResourceNotFound as exc:
        raise NotFoundError("Admin work queue not found") from exc


@router.post("/ui/orders/{order_id}/cancel")
async def ui_cancel_order(
    order_id: UUID,
    request: AdminCommentRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    order = await container.orders.cancel_order(
        order_id=order_id,
        actor_type="admin",
        actor_id=UUID(current[0].id),
        comment=request.comment,
    )
    return {"id": str(order.id), "status": order.status}


@router.post("/ui/orders/{order_id}/assign-performer")
async def ui_assign_performer(
    order_id: UUID,
    request: AdminAssignPerformerRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    match = await container.orders.invite_direct_performer_as_admin(
        order_id=order_id,
        performer_id=request.performer_id,
        admin_id=UUID(current[0].id),
        comment=request.comment,
    )
    return {"id": str(match.id), "status": match.status}


@router.post("/ui/orders/{order_id}/reassign-performer")
async def ui_reassign_performer(
    order_id: UUID,
    request: AdminAssignPerformerRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    match = await container.orders.reassign_performer_as_admin(
        order_id=order_id,
        performer_id=request.performer_id,
        admin_id=UUID(current[0].id),
        comment=request.comment,
    )
    return {"id": str(match.id), "status": match.status}


@router.post("/ui/orders/{order_id}/force-close")
async def ui_force_close_order(
    order_id: UUID,
    request: AdminCommentRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    order = await container.orders.force_close_order(
        order_id=order_id,
        comment=request.comment,
        admin_id=UUID(current[0].id),
    )
    return {"id": str(order.id), "status": order.status}


@router.post("/ui/orders/{order_id}/start")
async def ui_start_order(
    order_id: UUID,
    request: AdminOrderPerformerActionRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    order = await container.orders.start_order_as_admin(
        order_id=order_id,
        performer_id=request.performer_id,
        admin_id=UUID(current[0].id),
        comment=request.comment,
    )
    return {"id": str(order.id), "status": order.status}


@router.post("/ui/orders/{order_id}/finish")
async def ui_finish_order(
    order_id: UUID,
    request: AdminOrderPerformerActionRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    order = await container.orders.finish_order_as_admin(
        order_id=order_id,
        performer_id=request.performer_id,
        admin_id=UUID(current[0].id),
        comment=request.comment,
    )
    return {"id": str(order.id), "status": order.status}


@router.post("/ui/orders/{order_id}/manual-payout")
async def ui_manual_payout(
    order_id: UUID,
    request: AdminManualPayoutRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str | None]:
    payout = await container.payments.mark_manual_payout(
        order_id=order_id,
        reference=request.reference,
        comment=request.comment,
        admin_id=UUID(current[0].id),
    )
    return {
        "id": str(payout.order_id),
        "status": payout.status,
        "amount": str(payout.amount),
        "reference": payout.reference,
    }


@router.post("/ui/orders/{order_id}/payout/block")
async def ui_block_payout(
    order_id: UUID,
    request: AdminPayoutDecisionRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str | None]:
    order = await container.payments.set_payout_block(
        order_id=order_id,
        blocked=True,
        reason=request.reason,
        admin_id=UUID(current[0].id),
    )
    return {
        "id": str(order.id),
        "status": order.payout_status,
        "reason": order.payout_block_reason,
    }


@router.post("/ui/orders/{order_id}/payout/allow")
async def ui_allow_payout(
    order_id: UUID,
    request: AdminPayoutDecisionRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str | None]:
    order = await container.payments.set_payout_block(
        order_id=order_id,
        blocked=False,
        reason=request.reason,
        admin_id=UUID(current[0].id),
    )
    return {
        "id": str(order.id),
        "status": order.payout_status,
        "reason": order.payout_block_reason,
    }


@router.post("/ui/payments/{payment_id}/refund")
async def ui_refund(
    payment_id: UUID,
    request: AdminRefundRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> ManualRefundResponse:
    refund = await container.payments.create_manual_refund(
        CreateManualRefundCommand(
            payment_id=payment_id,
            amount=Decimal(request.amount) if request.amount is not None else None,
            reason=request.reason,
            admin_id=UUID(current[0].id),
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


@router.post("/ui/payments/{payment_id}/retry-check")
async def ui_retry_payment_check(
    payment_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> PaymentRetryResponse:
    result = await container.payments.retry_payment_operation(
        command=RetryPaymentOperationCommand(payment_id=payment_id),
        admin_id=UUID(current[0].id),
    )
    return PaymentRetryResponse(
        status=result.status if result is not None else "checked",
        applied=result.applied if result is not None else False,
        unapplied_reason=result.unapplied_reason if result is not None else None,
    )


@router.post("/ui/performers/{performer_id}/activate")
async def ui_activate_performer(
    performer_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    performer = await container.performers.activate_performer(
        performer_id, audit_admin_id=UUID(current[0].id)
    )
    return {"id": str(performer.id), "status": performer.status}


@router.post("/ui/performers/{performer_id}/pause")
async def ui_pause_performer(
    performer_id: UUID,
    request: AdminCommentRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str | bool]:
    performer = await container.performers.set_accepting_orders_as_admin(
        performer_id=performer_id,
        is_accepting_orders=False,
        admin_id=UUID(current[0].id),
        comment=request.comment,
    )
    return {
        "id": str(performer.id),
        "status": performer.status,
        "is_accepting_orders": performer.is_accepting_orders,
    }


@router.post("/ui/performers/{performer_id}/resume")
async def ui_resume_performer(
    performer_id: UUID,
    request: AdminCommentRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str | bool]:
    performer = await container.performers.set_accepting_orders_as_admin(
        performer_id=performer_id,
        is_accepting_orders=True,
        admin_id=UUID(current[0].id),
        comment=request.comment,
    )
    return {
        "id": str(performer.id),
        "status": performer.status,
        "is_accepting_orders": performer.is_accepting_orders,
    }


@router.post("/ui/performers/{performer_id}/block")
async def ui_block_performer(
    performer_id: UUID,
    request: AdminPerformerDecisionRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str | bool]:
    performer = await container.performers.block_performer(
        performer_id=performer_id,
        reason=request.reason,
        comment=request.comment,
        admin_id=UUID(current[0].id),
    )
    return {
        "id": str(performer.id),
        "status": performer.status,
        "is_accepting_orders": performer.is_accepting_orders,
    }


@router.post("/ui/performers/{performer_id}/unblock")
async def ui_unblock_performer(
    performer_id: UUID,
    request: AdminCommentRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str | bool]:
    performer = await container.performers.unblock_performer(
        performer_id=performer_id,
        comment=request.comment,
        admin_id=UUID(current[0].id),
    )
    return {
        "id": str(performer.id),
        "status": performer.status,
        "is_accepting_orders": performer.is_accepting_orders,
    }


@router.post("/ui/customers/{customer_id}/block")
async def ui_block_customer(
    customer_id: UUID,
    request: AdminPerformerDecisionRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, Any]:
    return await container.admin.block_customer(
        customer_id=customer_id,
        reason=request.reason,
        comment=request.comment,
        admin_id=UUID(current[0].id),
    )


@router.post("/ui/customers/{customer_id}/unblock")
async def ui_unblock_customer(
    customer_id: UUID,
    request: AdminCommentRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, Any]:
    return await container.admin.unblock_customer(
        customer_id=customer_id,
        comment=request.comment,
        admin_id=UUID(current[0].id),
    )


@router.patch("/ui/performers/{performer_id}/profile")
async def ui_update_performer_profile(
    performer_id: UUID,
    request: AdminPerformerProfileRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    performer = await container.performers.update_performer_profile_as_admin(
        performer_id=performer_id,
        phone=request.phone,
        contact_method=request.contact_method,
        admin_id=UUID(current[0].id),
        comment=request.comment,
    )
    return {"id": str(performer.id), "status": performer.status}


@router.post("/ui/performers/{performer_id}/reject")
async def ui_reject_performer(
    performer_id: UUID,
    request: AdminPerformerRejectRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    performer = await container.performers.reject_performer(
        performer_id=performer_id,
        reason=request.reason,
        comment=request.comment,
        admin_id=UUID(current[0].id),
    )
    return {"id": str(performer.id), "status": performer.status}


@router.post("/ui/performers/{performer_id}/services/{service_id}/approve")
async def ui_approve_service(
    performer_id: UUID,
    service_id: UUID,
    request: AdminPerformerServiceRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    service = await container.performers.approve_performer_service(
        ApprovePerformerServiceCommand(
            performer_id=performer_id,
            service_id=service_id,
            admin_max_objects=request.admin_max_objects,
            constraints=request.constraints,
            approved_by_admin_id=UUID(current[0].id),
        ),
        audit_admin_id=UUID(current[0].id),
    )
    return {"id": str(service.id), "status": "approved"}


@router.post("/ui/performers/{performer_id}/services", status_code=201)
async def ui_add_performer_service(
    performer_id: UUID,
    request: AdminAddPerformerServiceRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str | int | bool]:
    service = await container.performers.add_performer_service_as_admin(
        performer_id=performer_id,
        service_id=request.service_id,
        admin_max_objects=request.admin_max_objects,
        constraints=request.constraints,
        admin_id=UUID(current[0].id),
        comment=request.comment,
    )
    return {
        "id": str(service.id),
        "service_id": str(service.service_id),
        "status": "approved",
        "is_enabled": service.is_enabled,
        "admin_max_objects": service.admin_max_objects,
    }


@router.post("/ui/performers/{performer_id}/services/{service_id}/revoke")
async def ui_revoke_service(
    performer_id: UUID,
    service_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    service = await container.performers.revoke_performer_service(
        performer_id=performer_id,
        service_id=service_id,
        audit_admin_id=UUID(current[0].id),
    )
    return {"id": str(service.id), "status": "revoked"}


@router.post("/ui/performers/{performer_id}/services/{service_id}/enable")
async def ui_enable_service(
    performer_id: UUID,
    service_id: UUID,
    request: AdminCommentRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str | bool]:
    service = await container.performers.set_service_enabled_as_admin(
        performer_id=performer_id,
        service_id=service_id,
        is_enabled=True,
        admin_id=UUID(current[0].id),
        comment=request.comment,
    )
    return {
        "id": str(service.id),
        "status": "enabled",
        "is_enabled": service.is_enabled,
    }


@router.post("/ui/performers/{performer_id}/services/{service_id}/disable")
async def ui_disable_service(
    performer_id: UUID,
    service_id: UUID,
    request: AdminCommentRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str | bool]:
    service = await container.performers.set_service_enabled_as_admin(
        performer_id=performer_id,
        service_id=service_id,
        is_enabled=False,
        admin_id=UUID(current[0].id),
        comment=request.comment,
    )
    return {
        "id": str(service.id),
        "status": "disabled",
        "is_enabled": service.is_enabled,
    }


@router.patch("/ui/performers/{performer_id}/services/{service_id}/limits")
async def ui_update_service_limits(
    performer_id: UUID,
    service_id: UUID,
    request: AdminPerformerServiceLimitsRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str | int]:
    service = await container.performers.set_service_max_objects_as_admin(
        performer_id=performer_id,
        service_id=service_id,
        performer_max_objects=request.performer_max_objects,
        admin_id=UUID(current[0].id),
        comment=request.comment,
    )
    return {
        "id": str(service.id),
        "status": "updated",
        "performer_max_objects": service.performer_max_objects,
    }


@router.put("/ui/performers/{performer_id}/schedule")
async def ui_set_schedule(
    performer_id: UUID,
    request: AdminPerformerScheduleRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    schedule = await container.performers.set_schedule_as_admin(
        performer_id,
        lambda telegram_id: SetPerformerScheduleCommand(
            telegram_id=telegram_id,
            schedule_type=request.schedule_type,
            work_days=tuple(request.work_days)
            if request.work_days is not None
            else None,
            work_start_time=request.work_start_time,
            work_end_time=request.work_end_time,
        ),
        audit_admin_id=UUID(current[0].id),
    )
    return {"id": str(schedule.id), "status": "updated"}


@router.post("/ui/performers/{performer_id}/calendar-overrides")
async def ui_add_calendar_override(
    performer_id: UUID,
    request: AdminPerformerCalendarOverrideRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    override = await container.performers.add_override_as_admin(
        performer_id,
        lambda telegram_id: AddCalendarOverrideCommand(
            telegram_id=telegram_id,
            override_type=request.override_type,
            starts_at=request.starts_at,
            ends_at=request.ends_at,
            comment=request.comment,
        ),
        audit_admin_id=UUID(current[0].id),
    )
    return {"id": str(override.id), "status": "created"}


@router.post("/ui/invitations")
async def ui_create_invitation(
    request: AdminInvitationRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str | None]:
    invitation = await container.performers.create_invitation(
        CreateInvitationCommand(
            telegram_id=request.telegram_id,
            created_by_admin_id=UUID(current[0].id),
            expires_at=request.expires_at,
        ),
        audit_admin_id=UUID(current[0].id),
    )
    return {
        "id": str(invitation.id),
        "status": invitation.status,
        "expires_at": invitation.expires_at.isoformat()
        if invitation.expires_at
        else None,
    }


@router.patch("/ui/support/{kind}/{record_id}")
async def ui_update_support(
    kind: str,
    record_id: UUID,
    request: AdminSupportUpdateRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    record = await container.support.update_support_record(
        record_kind=kind,
        record_id=record_id,
        status=request.status,
        admin_comment=request.comment,
        admin_id=UUID(current[0].id),
    )
    return {"id": str(record.id), "status": record.status}


@router.post("/ui/deletions/{record_id}/resolve")
async def ui_resolve_deletion(
    record_id: UUID,
    request: AdminCommentRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    record = await container.support.resolve_deletion_request(
        record_id=record_id,
        admin_comment=request.comment,
        admin_id=UUID(current[0].id),
    )
    return {"id": str(record.id), "status": record.status}


@router.post("/ui/deletions/{record_id}/anonymize")
async def ui_anonymize_deletion(
    record_id: UUID,
    request: AdminCommentRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    record = await container.support.anonymize_deletion_request(
        record_id=record_id,
        admin_comment=request.comment,
        admin_id=UUID(current[0].id),
    )
    return {"id": str(record.id), "status": record.status}


@router.post("/ui/files/{file_id}/hide")
async def ui_hide_file(
    file_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, str]:
    await container.admin.hide_file(file_id, admin_id=UUID(current[0].id))
    return {"id": str(file_id), "status": "deleted"}


@router.get("/ui/files/{file_id}/download-url")
async def ui_file_download_url(
    file_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
) -> dict[str, Any]:
    return await container.admin.get_file_download_url(
        file_id,
        admin_id=UUID(current[0].id),
    )


@router.patch("/ui/settings/{key}")
async def ui_update_setting(
    key: str,
    request: UpdateBusinessSettingRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> BusinessSettingResponse:
    return await container.admin.update_business_setting(
        key=key,
        value=request.value,
        admin_id=UUID(current[0].id),
    )


@router.get("/ui/notifications")
async def list_ui_notifications(
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> AdminNotificationPageResponse:
    items, total = await container.admin.list_admin_notifications(
        admin_id=UUID(current[0].id),
        status=None,
        is_read=None,
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
                attempts=getattr(item, "attempts", 0),
                admin_retry_count=getattr(item, "admin_retry_count", 0),
            )
            for item in items
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/ui/notifications/read")
async def mark_ui_notifications_read(
    request: MarkAdminNotificationsReadRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> MarkAdminNotificationsReadResponse:
    marked = await container.admin.mark_admin_notifications_read(
        admin_id=UUID(current[0].id),
        notification_ids=request.ids,
    )
    return MarkAdminNotificationsReadResponse(marked=marked)


@router.post("/ui/notifications/{notification_id}/retry")
async def retry_ui_notification(
    notification_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, Any]:
    return await container.admin.retry_admin_notification(
        notification_id,
        admin_id=UUID(current[0].id),
    )


@router.patch("/ui/catalog/services/{service_id}")
async def ui_update_catalog_service(
    service_id: UUID,
    request: AdminCatalogServiceRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, Any]:
    return await container.admin.update_catalog_service(
        service_id=service_id,
        changes=request.model_dump(exclude_none=True),
        admin_id=UUID(current[0].id),
        reason=request.comment,
    )


@router.patch("/ui/catalog/service-options/{option_id}")
async def ui_update_catalog_service_option(
    option_id: UUID,
    request: AdminCatalogServiceOptionRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, Any]:
    return await container.admin.update_catalog_service_option(
        option_id=option_id,
        changes=request.model_dump(exclude_none=True),
        admin_id=UUID(current[0].id),
        reason=request.comment,
    )


@router.patch("/ui/catalog/cities/{city_id}")
async def ui_update_catalog_city(
    city_id: UUID,
    request: AdminCatalogCityRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, Any]:
    return await container.admin.update_catalog_city(
        city_id=city_id,
        changes=request.model_dump(exclude_none=True),
        admin_id=UUID(current[0].id),
        reason=request.comment,
    )


@router.patch("/ui/catalog/{resource}/{entity_id}")
async def ui_update_catalog_resource(
    resource: str,
    entity_id: UUID,
    request: AdminCatalogResourceUpdateRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, Any]:
    return await container.admin.update_catalog_resource(
        resource=resource,
        entity_id=entity_id,
        changes=request.changes,
        admin_id=UUID(current[0].id),
        reason=request.comment,
    )


@router.post("/ui/violations")
async def ui_create_violation(
    request: AdminViolationRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, Any]:
    return await container.admin.create_violation(
        account_type=request.account_type,
        customer_id=request.customer_id,
        performer_id=request.performer_id,
        order_id=request.order_id,
        case_type=request.case_type,
        case_id=request.case_id,
        violation_type=request.violation_type,
        action=request.action,
        reason=request.reason,
        admin_id=UUID(current[0].id),
    )


@router.post("/ui/violations/{violation_id}/resolve")
async def ui_resolve_violation(
    violation_id: UUID,
    request: AdminViolationResolveRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> dict[str, Any]:
    return await container.admin.resolve_violation(
        violation_id=violation_id,
        comment=request.comment,
        admin_id=UUID(current[0].id),
    )


@router.get("/ui/{resource}")
async def list_ui_resource(
    resource: str,
    container: Annotated[Container, Depends(get_container)],
    _current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    query: str | None = None,
    status: str | None = None,
) -> AdminResourcePageResponse:
    try:
        items, total = await container.admin.list_ui_resource(
            resource,
            page=page,
            page_size=page_size,
            query=query,
            status=status,
        )
    except AdminResourceNotFound as exc:
        raise NotFoundError("Admin resource not found") from exc
    return AdminResourcePageResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/ui/{resource}/{entity_id}")
async def get_ui_resource(
    resource: str,
    entity_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    _current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
) -> AdminResourceDetailResponse:
    try:
        result = await container.admin.get_ui_resource(resource, entity_id)
    except AdminResourceNotFound as exc:
        raise NotFoundError("Admin resource not found") from exc
    return AdminResourceDetailResponse(**result)


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
                attempts=getattr(item, "attempts", 0),
                admin_retry_count=getattr(item, "admin_retry_count", 0),
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


@router.post("/orders/payouts/manual")
async def mark_manual_payout(
    request: ManualPayoutRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> ManualPayoutResponse:
    payout = await container.payments.mark_manual_payout(
        order_id=request.order_id,
        reference=request.reference,
        comment=request.comment,
        admin_id=UUID(current[0].id),
    )
    return ManualPayoutResponse(
        order_id=str(payout.order_id),
        status=payout.status,
        amount=str(payout.amount),
        reference=payout.reference,
        comment=payout.comment,
        completed_at=payout.completed_at.isoformat(),
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

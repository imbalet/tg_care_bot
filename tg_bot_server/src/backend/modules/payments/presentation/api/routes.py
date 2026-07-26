from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key
from backend.modules.payments.application import (
    GetCustomerPaymentStatusCommand,
    PaymentWebhookCommand,
)
from backend.modules.payments.infrastructure import verify_tbank_token

from .schemas import PaymentStatusResponse

router = APIRouter(prefix="/api/payments", tags=["payments"])

SUCCESS_STATUSES = {"CONFIRMED", "AUTHORIZED"}


@router.post("/webhooks/tbank")
async def tbank_webhook(
    request: Request,
    container: Annotated[Container, Depends(get_container)],
) -> Response:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    settings = container.settings
    if str(payload.get("TerminalKey")) != settings.tbank_terminal_key:
        raise HTTPException(status_code=403, detail="Invalid terminal")
    if not verify_tbank_token(payload, settings.tbank_password):
        raise HTTPException(status_code=403, detail="Invalid token")
    status = str(payload.get("Status"))
    payment_id = payload.get("PaymentId")
    provider_order_id = payload.get("OrderId")
    if payment_id is None or provider_order_id is None:
        raise HTTPException(status_code=400, detail="Invalid payment webhook")
    try:
        order_id = UUID(str(provider_order_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook order") from exc
    amount = payload.get("Amount", 0)
    if payload.get("Success") is True and status in SUCCESS_STATUSES:
        parsed_amount = _parse_success_amount(amount)
    else:
        parsed_amount = Decimal("0")
    await container.payments.apply_payment_webhook(
        PaymentWebhookCommand(
            provider_payment_id=str(payment_id),
            provider_order_id=order_id,
            status=status,
            amount=parsed_amount,
            paid_at=_paid_at(payload),
            raw_payload=_safe_payload(payload),
        ),
    )
    return Response("OK", media_type="text/plain")


@router.get(
    "/orders/{order_id}/status",
    dependencies=[Depends(require_service_key)],
)
async def get_customer_payment_status(
    order_id: str,
    customer_id: str,
    container: Annotated[Container, Depends(get_container)],
) -> PaymentStatusResponse:
    result = await container.payments.get_customer_payment_status(
        GetCustomerPaymentStatusCommand(
            order_id=UUID(order_id),
            customer_id=UUID(customer_id),
        ),
    )
    return PaymentStatusResponse(
        order_id=str(result.order_id),
        order_status=result.order_status,
        payment_id=str(result.payment_id) if result.payment_id is not None else None,
        payment_status=result.payment_status,
        confirmation_url=result.confirmation_url,
        expires_at=result.expires_at.isoformat()
        if result.expires_at is not None
        else None,
        failure_code=result.failure_code,
        attempts_used=result.attempts_used,
        max_attempts=result.max_attempts,
        retry_available=result.retry_available,
    )


@router.post(
    "/orders/{order_id}/retry",
    dependencies=[Depends(require_service_key)],
)
async def retry_customer_payment(
    order_id: UUID,
    customer_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> PaymentStatusResponse:
    result = await container.payments.retry_customer_payment(
        order_id=order_id,
        customer_id=customer_id,
    )
    return PaymentStatusResponse(
        order_id=str(result.order_id),
        order_status=result.order_status,
        payment_id=str(result.payment_id) if result.payment_id is not None else None,
        payment_status=result.payment_status,
        confirmation_url=result.confirmation_url,
        expires_at=result.expires_at.isoformat()
        if result.expires_at is not None
        else None,
        failure_code=result.failure_code,
        attempts_used=result.attempts_used,
        max_attempts=result.max_attempts,
        retry_available=result.retry_available,
    )


def _paid_at(payload: dict[str, Any]) -> datetime:
    raw = payload.get("PaymentDate") or payload.get("Date")
    if isinstance(raw, str):
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


def _parse_success_amount(amount: object) -> Decimal:
    if isinstance(amount, bool):
        raise HTTPException(status_code=400, detail="Invalid webhook amount")
    if isinstance(amount, int):
        raw_amount = str(amount)
    elif (
        isinstance(amount, str)
        and amount
        and all("0" <= character <= "9" for character in amount)
    ):
        raw_amount = amount
    else:
        raise HTTPException(status_code=400, detail="Invalid webhook amount")
    if int(raw_amount) <= 0:
        raise HTTPException(status_code=400, detail="Invalid webhook amount")
    return Decimal(int(raw_amount)) / Decimal("100")


def _safe_payload(payload: dict[str, Any]) -> dict[str, object]:
    allowed = {"TerminalKey", "OrderId", "Success", "Status", "PaymentId", "Amount"}
    return {key: value for key, value in payload.items() if key in allowed}

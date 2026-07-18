from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.modules.payments.application import PaymentWebhookCommand
from backend.modules.payments.infrastructure import verify_tbank_token

from .schemas import PaymentWebhookResponse

router = APIRouter(prefix="/api/payments", tags=["payments"])

SUCCESS_STATUSES = {"CONFIRMED", "AUTHORIZED"}


@router.post("/webhooks/tbank")
async def tbank_webhook(
    request: Request,
    container: Annotated[Container, Depends(get_container)],
) -> PaymentWebhookResponse:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    settings = container.settings
    if str(payload.get("TerminalKey")) != settings.tbank_terminal_key:
        raise HTTPException(status_code=403, detail="Invalid terminal")
    if not verify_tbank_token(payload, settings.tbank_password):
        raise HTTPException(status_code=403, detail="Invalid token")
    if payload.get("Success") is not True:
        return PaymentWebhookResponse(status="ignored")
    status = str(payload.get("Status"))
    if status not in SUCCESS_STATUSES:
        return PaymentWebhookResponse(status="ignored")
    payment_id = payload.get("PaymentId")
    amount = payload.get("Amount")
    if payment_id is None or amount is None:
        raise HTTPException(status_code=400, detail="Invalid payment webhook")
    result = await container.services().apply_payment_webhook(
        PaymentWebhookCommand(
            provider_payment_id=str(payment_id),
            status=status,
            amount=Decimal(int(amount)) / Decimal("100"),
            paid_at=_paid_at(payload),
            raw_payload=_safe_payload(payload),
        ),
    )
    return PaymentWebhookResponse(status=result.status)


def _paid_at(payload: dict[str, Any]) -> datetime:
    raw = payload.get("PaymentDate") or payload.get("Date")
    if isinstance(raw, str):
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


def _safe_payload(payload: dict[str, Any]) -> dict[str, object]:
    allowed = {"TerminalKey", "OrderId", "Success", "Status", "PaymentId", "Amount"}
    return {key: value for key, value in payload.items() if key in allowed}

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx

from backend.common.domain import ValidationError
from backend.modules.payments.application import (
    PaymentGatewayConfirmCommand,
    PaymentGatewayConfirmResult,
    PaymentGatewayInitCommand,
    PaymentGatewayInitResult,
    PaymentGatewayRefundCommand,
    PaymentGatewayRefundResult,
    PaymentGatewayStateCommand,
    PaymentGatewayStateResult,
)


@dataclass(frozen=True)
class TBankReceiptSettings:
    taxation: str
    tax: str
    payment_method: str
    payment_object: str


class TBankPaymentGateway:
    def __init__(
        self,
        *,
        base_url: str,
        terminal_key: str,
        password: str,
        notification_url: str | None,
        receipt: TBankReceiptSettings,
        timeout_seconds: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._terminal_key = terminal_key
        self._password = password
        self._notification_url = notification_url
        self._receipt = receipt
        self._timeout_seconds = timeout_seconds

    async def create_payment(
        self,
        command: PaymentGatewayInitCommand,
    ) -> PaymentGatewayInitResult:
        payload: dict[str, Any] = {
            "TerminalKey": self._terminal_key,
            "Amount": _amount_to_kopecks(command.amount),
            "OrderId": str(command.payment_id),
            "PayType": "T",
            "Description": command.description[:250],
            "DATA": {
                "order_id": str(command.order_id),
                "payment_id": str(command.payment_id),
                "idempotency_key": command.idempotency_key,
            },
            "Receipt": {
                "Phone": command.customer_phone,
                "Taxation": self._receipt.taxation,
                "Items": [
                    {
                        "Name": command.description[:64],
                        "Price": _amount_to_kopecks(command.amount),
                        "Quantity": 1,
                        "Amount": _amount_to_kopecks(command.amount),
                        "Tax": self._receipt.tax,
                        "PaymentMethod": self._receipt.payment_method,
                        "PaymentObject": self._receipt.payment_object,
                    },
                ],
            },
        }
        if self._notification_url is not None:
            payload["NotificationURL"] = self._notification_url
        payload["Token"] = _sign_payload(payload, self._password)
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
        ) as client:
            response = await client.post("/Init", json=payload)
            response.raise_for_status()
        data = response.json()
        if data.get("Success") is not True:
            details = data.get("Details") or data.get("Message") or "unknown"
            raise ValidationError(f"T-Bank payment init failed: {details}")
        payment_id = data.get("PaymentId")
        payment_url = data.get("PaymentURL")
        if payment_id is None or payment_url is None:
            raise ValidationError("T-Bank payment init response is incomplete")
        return PaymentGatewayInitResult(
            provider_payment_id=str(payment_id),
            provider_deal_id=str(data["DealId"]) if data.get("DealId") else None,
            confirmation_url=str(payment_url),
        )

    async def create_refund(
        self,
        command: PaymentGatewayRefundCommand,
    ) -> PaymentGatewayRefundResult:
        payload: dict[str, Any] = {
            "TerminalKey": self._terminal_key,
            "PaymentId": command.provider_payment_id,
            "Amount": _amount_to_kopecks(command.amount),
            "DATA": {
                "refund_id": str(command.refund_id),
                "payment_id": str(command.payment_id),
                "idempotency_key": command.idempotency_key,
            },
        }
        payload["Token"] = _sign_payload(payload, self._password)
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
        ) as client:
            response = await client.post("/Cancel", json=payload)
            response.raise_for_status()
        data = response.json()
        if data.get("Success") is not True:
            details = data.get("Details") or data.get("Message") or "unknown"
            raise ValidationError(f"T-Bank refund failed: {details}")
        refund_id = data.get("PaymentId") or command.provider_payment_id
        return PaymentGatewayRefundResult(provider_refund_id=str(refund_id))

    async def confirm_payment(
        self,
        command: PaymentGatewayConfirmCommand,
    ) -> PaymentGatewayConfirmResult:
        payload: dict[str, Any] = {
            "TerminalKey": self._terminal_key,
            "PaymentId": command.provider_payment_id,
            "Amount": _amount_to_kopecks(command.amount),
        }
        payload["Token"] = _sign_payload(payload, self._password)
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
        ) as client:
            response = await client.post("/Confirm", json=payload)
            response.raise_for_status()
        data = response.json()
        if data.get("Success") is not True:
            details = data.get("Details") or data.get("Message") or "unknown"
            raise ValidationError(f"T-Bank confirm failed: {details}")
        payment_id = data.get("PaymentId")
        status = data.get("Status")
        if payment_id is None or status is None:
            raise ValidationError("T-Bank confirm response is incomplete")
        return PaymentGatewayConfirmResult(
            provider_payment_id=str(payment_id),
            status=str(status),
        )

    async def get_payment_state(
        self,
        command: PaymentGatewayStateCommand,
    ) -> PaymentGatewayStateResult:
        payload: dict[str, Any] = {
            "TerminalKey": self._terminal_key,
            "PaymentId": command.provider_payment_id,
        }
        payload["Token"] = _sign_payload(payload, self._password)
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
        ) as client:
            response = await client.post("/GetState", json=payload)
            response.raise_for_status()
        data = response.json()
        if data.get("Success") is not True:
            details = data.get("Details") or data.get("Message") or "unknown"
            raise ValidationError(f"T-Bank get state failed: {details}")
        amount = data.get("Amount")
        status = data.get("Status")
        payment_id = data.get("PaymentId")
        if amount is None or status is None or payment_id is None:
            raise ValidationError("T-Bank get state response is incomplete")
        return PaymentGatewayStateResult(
            provider_payment_id=str(payment_id),
            status=str(status),
            amount=Decimal(int(amount)) / Decimal("100"),
            paid_at=_provider_datetime(data.get("PaymentDate") or data.get("Date")),
        )


def verify_tbank_token(payload: dict[str, Any], password: str) -> bool:
    token = payload.get("Token")
    if not isinstance(token, str):
        return False
    return token.lower() == _sign_payload(payload, password).lower()


def _sign_payload(payload: dict[str, Any], password: str) -> str:
    sign_data = {
        key: value
        for key, value in payload.items()
        if key != "Token" and not isinstance(value, (dict, list))
    }
    sign_data["Password"] = password
    raw = "".join(str(sign_data[key]) for key in sorted(sign_data))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _amount_to_kopecks(amount: Decimal) -> int:
    return int((amount * Decimal("100")).quantize(Decimal("1"), ROUND_HALF_UP))


def _provider_datetime(raw: object) -> datetime:
    if isinstance(raw, str):
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)

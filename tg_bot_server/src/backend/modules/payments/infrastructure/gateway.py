import hashlib
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx

from backend.common.domain import ValidationError
from backend.modules.payments.application import (
    PaymentGatewayInitCommand,
    PaymentGatewayInitResult,
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
        receipt: TBankReceiptSettings,
        timeout_seconds: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._terminal_key = terminal_key
        self._password = password
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

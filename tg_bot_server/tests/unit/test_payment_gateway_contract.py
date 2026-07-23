from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
import pytest

from backend.common.domain import ValidationError
from backend.modules.payments.application import PaymentGatewayInitCommand
from backend.modules.payments.infrastructure import (
    TBankPaymentGateway,
    TBankReceiptSettings,
    verify_tbank_token,
)


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _Client:
    response: _Response
    requests: list[tuple[str, dict[str, Any]]]

    def __init__(self, **_: Any) -> None:
        self.requests = []

    async def __aenter__(self) -> _Client:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(self, path: str, *, json: dict[str, Any]) -> _Response:
        self.requests.append((path, json))
        return self.response


@pytest.mark.unit
async def test_tbank_init_builds_signed_idempotent_receipt_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    client.response = _Response(
        {"Success": True, "PaymentId": 42, "PaymentURL": "https://pay.test/42"},
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: client)
    gateway_password = str(uuid4())
    gateway = TBankPaymentGateway(
        base_url="https://bank.test/",
        terminal_key="terminal",
        password=gateway_password,
        notification_url="https://api.test/webhook",
        receipt=TBankReceiptSettings(
            taxation="usn_income",
            tax="none",
            payment_method="full_payment",
            payment_object="service",
        ),
        timeout_seconds=3,
    )
    command = PaymentGatewayInitCommand(
        payment_id=uuid4(),
        order_id=uuid4(),
        idempotency_key="payment:42",
        amount=Decimal("123.45"),
        description="Care service",
        customer_phone="+79990000000",
        customer_name="Customer",
    )

    result = await gateway.create_payment(command)

    assert result.provider_payment_id == "42"
    path, payload = client.requests[0]
    assert path == "/Init"
    assert payload["Amount"] == 12345
    assert payload["DATA"]["idempotency_key"] == "payment:42"
    assert payload["Receipt"]["Items"][0]["Amount"] == 12345
    assert payload["NotificationURL"] == "https://api.test/webhook"
    assert verify_tbank_token(payload, gateway_password)


@pytest.mark.unit
async def test_tbank_init_rejects_incomplete_provider_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    client.response = _Response({"Success": True, "PaymentId": 42})
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: client)
    gateway_password = str(uuid4())
    gateway = TBankPaymentGateway(
        base_url="https://bank.test",
        terminal_key="terminal",
        password=gateway_password,
        notification_url=None,
        receipt=TBankReceiptSettings("usn_income", "none", "full_payment", "service"),
        timeout_seconds=3,
    )

    with pytest.raises(ValidationError, match="response is incomplete"):
        await gateway.create_payment(
            PaymentGatewayInitCommand(
                payment_id=uuid4(),
                order_id=uuid4(),
                idempotency_key="payment:42",
                amount=Decimal("10.00"),
                description="Service",
                customer_phone="+79990000000",
                customer_name="Customer",
            ),
        )

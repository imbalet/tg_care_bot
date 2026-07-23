from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.common.domain import NotFoundError
from backend.modules.payments.application.dto import (
    PaymentAttemptDTO,
    PaymentInitializationData,
    PaymentWebhookCommand,
    PaymentWebhookResult,
)
from backend.modules.payments.application.use_cases import (
    ApplyPaymentWebhookUseCase,
    InitializePaymentCommand,
    InitializePaymentUseCase,
)
from tests.support.fakes import FakePaymentGateway


def _initialization_data(*, status: str = "created") -> PaymentInitializationData:
    payment_id = uuid4()
    return PaymentInitializationData(
        payment=PaymentAttemptDTO(
            id=payment_id,
            order_id=uuid4(),
            performer_id=uuid4(),
            attempt_number=1,
            provider="tbank_test",
            provider_payment_id=None,
            provider_deal_id=None,
            idempotency_key=f"payment:{payment_id}",
            amount=Decimal("1500.00"),
            status=status,
            confirmation_url=None,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        ),
        customer_phone="+79990000000",
        customer_name="Test Customer",
        service_name="Care service",
    )


@pytest.mark.unit
async def test_initialize_payment_sends_idempotent_command_and_persists_result() -> (
    None
):
    repository = AsyncMock()
    gateway = FakePaymentGateway()
    data = _initialization_data()
    repository.get_initialization_data.return_value = data

    await InitializePaymentUseCase(repository, gateway).execute(
        InitializePaymentCommand(data.payment.id),
    )

    assert gateway.created[0].idempotency_key == data.payment.idempotency_key
    repository.mark_provider_initialized.assert_awaited_once()
    assert (
        repository.mark_provider_initialized.await_args.kwargs["provider_payment_id"]
        == f"provider-{data.payment.id}"
    )


@pytest.mark.unit
async def test_initialize_payment_skips_already_initialized_attempt() -> None:
    repository = AsyncMock()
    gateway = FakePaymentGateway()
    data = _initialization_data(status="pending")
    repository.get_initialization_data.return_value = data

    await InitializePaymentUseCase(repository, gateway).execute(
        InitializePaymentCommand(data.payment.id),
    )

    assert gateway.created == []
    repository.mark_provider_initialized.assert_not_awaited()


@pytest.mark.unit
async def test_apply_webhook_maps_missing_payment_to_not_found() -> None:
    repository = AsyncMock()
    repository.apply_successful_webhook.return_value = None

    with pytest.raises(NotFoundError):
        await ApplyPaymentWebhookUseCase(repository).execute(
            PaymentWebhookCommand(
                provider_payment_id="provider-payment",
                provider_order_id=uuid4(),
                status="CONFIRMED",
                amount=Decimal("10.00"),
                paid_at=datetime.now(UTC),
                raw_payload={},
            ),
        )


@pytest.mark.unit
async def test_apply_webhook_returns_repository_idempotency_result() -> None:
    repository = AsyncMock()
    expected = PaymentWebhookResult(
        payment_id=uuid4(),
        order_id=uuid4(),
        status="succeeded",
        applied=False,
        unapplied_reason="already_applied",
    )
    repository.apply_successful_webhook.return_value = expected

    result = await ApplyPaymentWebhookUseCase(repository).execute(
        PaymentWebhookCommand(
            provider_payment_id="provider-payment",
            provider_order_id=expected.order_id,
            status="CONFIRMED",
            amount=Decimal("10.00"),
            paid_at=datetime.now(UTC),
            raw_payload={"PaymentId": "provider-payment"},
        ),
    )

    assert result == expected

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.common.domain import NotFoundError, ValidationError
from backend.modules.payments.application.dto import (
    PaymentAttemptDTO,
    PaymentInitializationData,
    PaymentWebhookCommand,
    PaymentWebhookResult,
    RefundDTO,
)
from backend.modules.payments.application.use_cases import (
    ApplyPaymentWebhookUseCase,
    CompleteManualRefundUseCase,
    CreateManualRefundCommand,
    CreateManualRefundUseCase,
    GetCustomerPaymentStatusCommand,
    GetCustomerPaymentStatusUseCase,
    InitializePaymentCommand,
    InitializePaymentUseCase,
    RetryCustomerPaymentCommand,
    RetryCustomerPaymentUseCase,
    RetryPaymentOperationCommand,
    RetryPaymentOperationUseCase,
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
            provider_status="NEW",
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


@pytest.mark.unit
async def test_initialize_payment_rejects_unsupported_provider_and_marks_failure() -> (
    None
):
    repository = AsyncMock()
    gateway = FakePaymentGateway()
    data = _initialization_data()
    data = replace(data, payment=replace(data.payment, provider="unknown"))
    repository.get_initialization_data.return_value = data

    with pytest.raises(ValidationError, match="not supported"):
        await InitializePaymentUseCase(repository, gateway).execute(
            InitializePaymentCommand(data.payment.id),
        )

    failing_gateway = AsyncMock()
    failing_gateway.create_payment.side_effect = RuntimeError("provider down")
    data = replace(data, payment=replace(data.payment, provider="tbank_test"))
    repository.get_initialization_data.return_value = data
    with pytest.raises(RuntimeError):
        await InitializePaymentUseCase(repository, failing_gateway).execute(
            InitializePaymentCommand(data.payment.id),
        )
    repository.mark_provider_initialization_failed.assert_awaited_once()


@pytest.mark.unit
async def test_manual_refund_success_and_failure_are_persisted() -> None:
    repository = AsyncMock()
    gateway = FakePaymentGateway()
    refund_dto = RefundDTO(
        id=uuid4(),
        order_id=uuid4(),
        payment_id=uuid4(),
        refund_type="full",
        amount=Decimal("10.00"),
        status="pending",
        reason="customer_request",
        provider_refund_id=None,
        idempotency_key="refund:1",
    )
    repository.create_manual_refund.return_value = refund_dto

    created = await CreateManualRefundUseCase(repository).execute(
        CreateManualRefundCommand(uuid4(), None, "customer_request", uuid4()),
    )
    assert created == refund_dto
    await CompleteManualRefundUseCase(repository, gateway).execute(
        refund_dto,
        "provider-payment",
    )
    repository.mark_refund_succeeded.assert_awaited_once()

    failing = AsyncMock()
    failing.create_refund.side_effect = RuntimeError("refund down")
    with pytest.raises(RuntimeError):
        await CompleteManualRefundUseCase(repository, failing).execute(
            refund_dto,
            "provider-payment",
        )
    repository.mark_refund_failed.assert_awaited_once_with(refund_id=refund_dto.id)


@pytest.mark.unit
async def test_payment_status_and_retry_cover_provider_state_branches() -> None:
    repository = AsyncMock()
    gateway = AsyncMock()
    data = _initialization_data()
    repository.get_initialization_data.return_value = data
    repository.get_customer_payment_status.return_value = None

    with pytest.raises(NotFoundError):
        await GetCustomerPaymentStatusUseCase(repository).execute(
            GetCustomerPaymentStatusCommand(uuid4(), uuid4()),
        )

    data = replace(
        data,
        payment=replace(data.payment, provider_payment_id="provider"),
    )
    repository.get_initialization_data.return_value = data
    applied = PaymentWebhookResult(
        payment_id=data.payment.id,
        order_id=data.payment.order_id,
        status="succeeded",
        applied=True,
        unapplied_reason=None,
    )
    gateway.get_payment_state.return_value = type(
        "State",
        (),
        {
            "provider_payment_id": "provider",
            "status": "CONFIRMED",
            "amount": Decimal("10.00"),
            "paid_at": datetime.now(UTC),
        },
    )()
    repository.apply_successful_webhook.return_value = applied
    result = await RetryPaymentOperationUseCase(repository, gateway).execute(
        RetryPaymentOperationCommand(data.payment.id),
    )
    assert result == applied

    gateway.get_payment_state.return_value = type(
        "State",
        (),
        {
            "provider_payment_id": "provider",
            "status": "REJECTED",
            "amount": Decimal("10.00"),
            "paid_at": datetime.now(UTC),
        },
    )()
    repository.apply_successful_webhook.return_value = None
    assert (
        await RetryPaymentOperationUseCase(repository, gateway).execute(
            RetryPaymentOperationCommand(data.payment.id),
        )
        is None
    )
    repository.mark_provider_status.assert_awaited_once()


@pytest.mark.unit
async def test_retry_payment_rejects_non_created_attempt_without_provider_id() -> None:
    repository = AsyncMock()
    gateway = AsyncMock()
    data = _initialization_data(status="pending")
    repository.get_initialization_data.return_value = data

    with pytest.raises(ValidationError, match="Provider payment id"):
        await RetryPaymentOperationUseCase(repository, gateway).execute(
            RetryPaymentOperationCommand(data.payment.id),
        )

    gateway.get_payment_state.assert_not_awaited()


@pytest.mark.unit
async def test_customer_retry_creates_a_new_attempt() -> None:
    repository = AsyncMock()
    expected = _initialization_data().payment
    repository.create_customer_retry_payment.return_value = expected
    command = RetryCustomerPaymentCommand(uuid4(), uuid4())

    result = await RetryCustomerPaymentUseCase(repository).execute(command)

    assert result == expected
    repository.create_customer_retry_payment.assert_awaited_once_with(
        order_id=command.order_id,
        customer_id=command.customer_id,
        max_attempts=3,
    )


@pytest.mark.unit
async def test_initialize_payment_maps_missing_attempt_to_not_found() -> None:
    repository = AsyncMock()
    gateway = AsyncMock()
    repository.get_initialization_data.return_value = None

    with pytest.raises(NotFoundError, match="Payment not found"):
        await InitializePaymentUseCase(repository, gateway).execute(
            InitializePaymentCommand(uuid4()),
        )

    gateway.create_payment.assert_not_awaited()

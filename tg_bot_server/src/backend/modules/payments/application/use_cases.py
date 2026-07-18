from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from backend.common.domain import NotFoundError, ValidationError
from backend.modules.payments.application.dto import (
    PaymentGatewayInitCommand,
    PaymentGatewayRefundCommand,
    PaymentWebhookCommand,
    PaymentWebhookResult,
    RefundDTO,
)
from backend.modules.payments.application.interfaces import (
    PaymentGateway,
    PaymentRepository,
)


@dataclass(frozen=True)
class InitializePaymentCommand:
    payment_id: UUID


class InitializePaymentUseCase:
    def __init__(
        self,
        repository: PaymentRepository,
        gateway: PaymentGateway,
    ) -> None:
        self._repository = repository
        self._gateway = gateway

    async def execute(self, command: InitializePaymentCommand) -> None:
        data = await self._repository.get_initialization_data(command.payment_id)
        if data is None:
            raise NotFoundError("Payment not found")
        if data.payment.status != "created":
            return
        if data.payment.provider != "tbank_test":
            raise ValidationError("Payment provider is not supported")
        description = f"Оплата заказа {data.payment.order_id} ({data.service_name})"
        try:
            result = await self._gateway.create_payment(
                PaymentGatewayInitCommand(
                    payment_id=data.payment.id,
                    order_id=data.payment.order_id,
                    idempotency_key=data.payment.idempotency_key,
                    amount=data.payment.amount,
                    description=description,
                    customer_phone=data.customer_phone,
                    customer_name=data.customer_name,
                ),
            )
        except Exception:
            await self._repository.mark_provider_initialization_failed(
                payment_id=data.payment.id,
                failure_code="provider_init_failed",
            )
            raise
        await self._repository.mark_provider_initialized(
            payment_id=data.payment.id,
            provider_payment_id=result.provider_payment_id,
            provider_deal_id=result.provider_deal_id,
            confirmation_url=result.confirmation_url,
        )


class ApplyPaymentWebhookUseCase:
    def __init__(self, repository: PaymentRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        command: PaymentWebhookCommand,
    ) -> PaymentWebhookResult:
        result = await self._repository.apply_successful_webhook(command)
        if result is None:
            raise NotFoundError("Payment not found")
        return result


@dataclass(frozen=True)
class CreateManualRefundCommand:
    payment_id: UUID
    amount: Decimal
    reason: str
    admin_id: UUID


class CreateManualRefundUseCase:
    def __init__(self, repository: PaymentRepository) -> None:
        self._repository = repository

    async def execute(self, command: CreateManualRefundCommand) -> RefundDTO:
        if command.amount <= 0:
            raise ValidationError("Refund amount must be positive")
        return await self._repository.create_manual_refund(
            payment_id=command.payment_id,
            amount=command.amount,
            reason=command.reason,
            admin_id=command.admin_id,
        )


class CompleteManualRefundUseCase:
    def __init__(
        self,
        repository: PaymentRepository,
        gateway: PaymentGateway,
    ) -> None:
        self._repository = repository
        self._gateway = gateway

    async def execute(self, refund: RefundDTO, provider_payment_id: str) -> None:
        if refund.status != "pending":
            return
        try:
            result = await self._gateway.create_refund(
                PaymentGatewayRefundCommand(
                    refund_id=refund.id,
                    payment_id=refund.payment_id,
                    provider_payment_id=provider_payment_id,
                    idempotency_key=refund.idempotency_key,
                    amount=refund.amount,
                ),
            )
        except Exception:
            await self._repository.mark_refund_failed(refund_id=refund.id)
            raise
        await self._repository.mark_refund_succeeded(
            refund_id=refund.id,
            provider_refund_id=result.provider_refund_id,
        )

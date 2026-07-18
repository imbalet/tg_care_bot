from dataclasses import dataclass
from uuid import UUID

from backend.common.domain import NotFoundError, ValidationError
from backend.modules.payments.application.dto import PaymentGatewayInitCommand
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

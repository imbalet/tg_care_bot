from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.customers.infrastructure import CustomerModel
from backend.modules.orders.infrastructure.persistence.models import OrderModel
from backend.modules.payments.application import (
    PaymentAttemptDTO,
    PaymentInitializationData,
)
from backend.modules.payments.infrastructure.persistence.models import PaymentModel


class SqlAlchemyPaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_attempt_number(self, order_id: UUID) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(PaymentModel.attempt_number), 0)).where(
                PaymentModel.order_id == order_id,
            ),
        )
        return int(result.scalar_one()) + 1

    async def add(self, payment: PaymentModel) -> PaymentModel:
        self._session.add(payment)
        await self._session.flush()
        return payment

    async def get_initialization_data(
        self,
        payment_id: UUID,
    ) -> PaymentInitializationData | None:
        result = await self._session.execute(
            select(PaymentModel, OrderModel, CustomerModel)
            .join(OrderModel, OrderModel.id == PaymentModel.order_id)
            .join(CustomerModel, CustomerModel.id == OrderModel.customer_id)
            .where(PaymentModel.id == payment_id),
        )
        row = result.one_or_none()
        if row is None:
            return None
        payment, order, customer = row
        return PaymentInitializationData(
            payment=_payment_to_dto(payment),
            customer_phone=customer.phone,
            customer_name=customer.full_name,
            service_name=order.service_name,
        )

    async def mark_provider_initialized(
        self,
        *,
        payment_id: UUID,
        provider_payment_id: str,
        provider_deal_id: str | None,
        confirmation_url: str,
    ) -> None:
        payment = await self._session.get(PaymentModel, payment_id)
        if payment is None or payment.status != "created":
            return
        payment.provider_payment_id = provider_payment_id
        payment.provider_deal_id = provider_deal_id
        payment.confirmation_url = confirmation_url
        payment.status = "pending"
        payment.failure_code = None

    async def mark_provider_initialization_failed(
        self,
        *,
        payment_id: UUID,
        failure_code: str,
    ) -> None:
        payment = await self._session.get(PaymentModel, payment_id)
        if payment is None or payment.status != "created":
            return
        payment.failure_code = failure_code


def _payment_to_dto(model: PaymentModel) -> PaymentAttemptDTO:
    return PaymentAttemptDTO(
        id=model.id,
        order_id=model.order_id,
        performer_id=model.performer_id,
        attempt_number=model.attempt_number,
        provider=model.provider,
        provider_payment_id=model.provider_payment_id,
        provider_deal_id=model.provider_deal_id,
        idempotency_key=model.idempotency_key,
        amount=model.amount,
        status=model.status,
        confirmation_url=model.confirmation_url,
        expires_at=model.expires_at,
    )

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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

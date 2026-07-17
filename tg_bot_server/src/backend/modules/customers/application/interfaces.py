from typing import Protocol
from uuid import UUID

from backend.modules.customers.domain import Customer


class CustomerRepository(Protocol):
    async def get_by_telegram_id(self, telegram_id: int) -> Customer | None:
        pass

    async def get_city_is_active(self, city_id: UUID) -> bool:
        pass

    async def list_active_legal_document_ids(self) -> tuple[UUID, ...]:
        pass

    async def add(self, customer: Customer) -> None:
        pass

    async def add_legal_acceptances(
        self,
        *,
        customer_id: UUID,
        document_ids: tuple[UUID, ...],
    ) -> None:
        pass

    async def update(self, customer: Customer) -> None:
        pass

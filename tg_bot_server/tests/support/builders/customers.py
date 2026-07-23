from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from backend.modules.customers.infrastructure import CustomerModel


@dataclass(frozen=True)
class CustomerBuilder:
    """Build explicit customer entities for persistence scenarios."""

    def customer(
        self,
        *,
        city_id: UUID,
        customer_id: UUID | None = None,
        telegram_id: int = 100000001,
        full_name: str = "Test Customer",
        phone: str = "+79990000000",
        contact_method: str = "telegram",
    ) -> CustomerModel:
        return CustomerModel(
            id=customer_id or uuid4(),
            telegram_id=telegram_id,
            full_name=full_name,
            phone=phone,
            contact_method=contact_method,
            city_id=city_id,
        )

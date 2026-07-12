from decimal import Decimal
from typing import Protocol
from uuid import UUID

from backend.modules.orders.application.dto import ServicePricingDTO


class PricingRepository(Protocol):
    async def get_service_pricing(self, service_id: UUID) -> ServicePricingDTO | None:
        pass

    async def get_object_multiplier(
        self,
        *,
        category_id: UUID,
        objects_count: int,
    ) -> Decimal | None:
        pass

    async def get_decimal_setting(self, key: str) -> Decimal | None:
        pass

    async def get_integer_setting(self, key: str) -> int | None:
        pass


__all__ = ["PricingRepository"]

from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from backend.modules.orders.application.dto import (
    DraftOrderData,
    OrderCareObjectSnapshot,
    OrderDTO,
    PricePreviewDTO,
    ServicePricingDTO,
)


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


class OrderRepository(Protocol):
    async def get_order(self, order_id: UUID) -> OrderDTO | None:
        pass

    async def create_draft(
        self,
        *,
        data: DraftOrderData,
        service: ServicePricingDTO,
        price: PricePreviewDTO,
        object_snapshots: tuple[OrderCareObjectSnapshot, ...],
        matching_deadline_minutes: int,
    ) -> OrderDTO:
        pass

    async def replace_draft(
        self,
        *,
        order_id: UUID,
        data: DraftOrderData,
        service: ServicePricingDTO,
        price: PricePreviewDTO,
        object_snapshots: tuple[OrderCareObjectSnapshot, ...],
        matching_deadline_minutes: int,
    ) -> OrderDTO | None:
        pass

    async def cancel_draft(self, order_id: UUID) -> OrderDTO | None:
        pass

    async def publish_pool(self, order_id: UUID) -> OrderDTO | None:
        pass

    async def publish_direct(
        self,
        *,
        order_id: UUID,
        performer_id: UUID,
        response_window_minutes: int,
    ) -> OrderDTO | None:
        pass

    async def list_care_object_snapshots(
        self,
        *,
        customer_id: UUID,
        care_object_ids: tuple[UUID, ...],
    ) -> tuple[OrderCareObjectSnapshot, ...]:
        pass

    async def customer_address_is_active(
        self,
        *,
        customer_id: UUID,
        address_id: UUID,
    ) -> bool:
        pass

    async def service_options_exist(
        self,
        *,
        service_id: UUID,
        option_values: dict[UUID, Any],
    ) -> bool:
        pass


__all__ = ["OrderRepository", "PricingRepository"]

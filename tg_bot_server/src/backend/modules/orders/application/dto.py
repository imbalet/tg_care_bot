from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class ServicePricingDTO:
    service_id: UUID
    category_id: UUID
    service_code: str
    service_name: str
    price_type: str
    base_price: Decimal
    duration_step_minutes: int
    min_duration_minutes: int | None
    max_duration_minutes: int | None
    is_active: bool


@dataclass(frozen=True)
class PricePreviewDTO:
    service_id: UUID
    service_code: str
    service_name: str
    price_type: str
    duration_minutes: int
    billable_minutes: int | None
    started_24h_units: int | None
    objects_count: int
    object_multiplier: Decimal
    base_price: Decimal
    service_amount: Decimal
    platform_fee_percent: Decimal
    platform_fee_amount: Decimal
    performer_amount: Decimal
    total_amount: Decimal
    hold_limit_checked: bool


__all__ = ["PricePreviewDTO", "ServicePricingDTO"]

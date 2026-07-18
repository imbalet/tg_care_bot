from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ServicePricingDTO:
    service_id: UUID
    category_id: UUID
    category_object_type: str
    max_objects_per_order: int
    service_code: str
    service_name: str
    price_type: str
    base_price: Decimal
    location_policy: str
    schedule_policy: str
    photo_policy: str
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


@dataclass(frozen=True)
class OrderCareObjectSnapshot:
    care_object_id: UUID
    object_type: str
    display_name_at_order: str | None
    summary_at_order: str | None


@dataclass(frozen=True)
class OrderData:
    customer_id: UUID
    service_id: UUID
    start_at: datetime
    end_at: datetime
    care_object_ids: tuple[UUID, ...]
    address_id: UUID | None
    customer_comment: str | None
    report_photo_consent: bool | None
    option_values: dict[UUID, Any]


@dataclass(frozen=True)
class OrderDTO:
    id: UUID
    customer_id: UUID | None
    service_id: UUID
    service_code: str
    service_name: str
    schedule_policy: str
    photo_policy: str | None
    matching_mode: str | None
    status: str
    address_id: UUID | None
    location_source: str
    start_at: datetime
    end_at: datetime
    objects_count: int
    total_amount: Decimal
    performer_amount: Decimal
    platform_fee_amount: Decimal
    matching_deadline_at: datetime

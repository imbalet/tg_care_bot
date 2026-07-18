from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PricePreviewRequest(BaseModel):
    service_id: UUID
    start_at: datetime
    end_at: datetime
    objects_count: int = Field(ge=1)


class OrderRequest(BaseModel):
    customer_id: UUID
    service_id: UUID
    start_at: datetime
    end_at: datetime
    care_object_ids: list[UUID] = Field(min_length=1)
    address_id: UUID | None = None
    customer_comment: str | None = Field(default=None, max_length=2000)
    report_photo_consent: bool | None = None
    option_values: dict[UUID, Any] = Field(default_factory=dict)


class DirectOrderRequest(OrderRequest):
    performer_id: UUID


class OrderResponse(BaseModel):
    id: str
    customer_id: str | None
    service_id: str
    service_code: str
    service_name: str
    schedule_policy: str
    photo_policy: str | None
    matching_mode: str | None
    status: str
    address_id: str | None
    location_source: str
    start_at: str
    end_at: str
    objects_count: int
    total_amount: Decimal
    performer_amount: Decimal
    platform_fee_amount: Decimal
    matching_deadline_at: str


class PricePreviewResponse(BaseModel):
    service_id: str
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

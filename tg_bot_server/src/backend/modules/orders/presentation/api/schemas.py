from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PricePreviewRequest(BaseModel):
    customer_id: UUID
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
    timezone: str


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


class PerformerMatchActionRequest(BaseModel):
    performer_id: UUID


class CustomerMatchActionRequest(BaseModel):
    customer_id: UUID


class CustomerDirectPerformerRequest(BaseModel):
    customer_id: UUID
    performer_id: UUID


class PerformerOrderActionRequest(BaseModel):
    performer_id: UUID


class CancelOrderRequest(BaseModel):
    actor_type: str = Field(pattern="^(customer|performer|admin)$")
    actor_id: UUID


class OrderReportRequest(BaseModel):
    performer_id: UUID
    completed_work: str = Field(min_length=1, max_length=10000)
    comment: str | None = Field(default=None, max_length=10000)
    problem_flag: bool = False
    problem_description: str | None = Field(default=None, max_length=10000)
    file_ids: list[UUID] = Field(default_factory=list, max_length=10)


class OrderReportResponse(BaseModel):
    id: str
    order_id: str
    performer_id: str
    completed_work: str
    comment: str | None
    problem_flag: bool
    problem_description: str | None
    submitted_at: str
    file_ids: list[str]


class OrderMatchResponse(BaseModel):
    id: str
    order_id: str
    performer_id: str
    source: str
    status: str
    starts_at: str
    ends_at: str
    response_expires_at: str
    selected_at: str | None
    closed_at: str | None
    close_reason: str | None
    timezone: str


class PaymentPromptResponse(BaseModel):
    payment_id: str
    confirmation_url: str | None
    expires_at: str
    timezone: str


class MatchActionResponse(BaseModel):
    order: OrderResponse
    match: OrderMatchResponse
    payment: PaymentPromptResponse | None


class MyOrderSummaryResponse(BaseModel):
    id: str
    service_name: str
    matching_mode: str | None
    status: str
    start_at: str
    end_at: str
    objects_count: int
    total_amount: Decimal
    payment_deadline_at: str | None
    matching_deadline_at: str
    timezone: str


class MyOrderCardResponse(MyOrderSummaryResponse):
    payment_status: str | None
    payment_confirmation_url: str | None
    payment_expires_at: str | None


class MyOrdersPageResponse(BaseModel):
    items: list[MyOrderSummaryResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int

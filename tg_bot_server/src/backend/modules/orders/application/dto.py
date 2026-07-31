from dataclasses import dataclass, field
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
    timezone: str
    location_source: str = "customer_address"


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
    timezone: str
    report_photo_consent: bool | None = None
    distance_km: Decimal | None = None
    price_type: str = field(default="hourly", kw_only=True)


@dataclass(frozen=True)
class PerformerServiceProfileDTO:
    service_id: UUID
    service_name: str
    price_type: str
    base_price: Decimal
    performer_max_objects: int


@dataclass(frozen=True)
class CustomerPerformerProfileDTO:
    performer_id: UUID
    full_name: str
    about_text: str | None
    city_name: str
    avatar_url: str | None
    services: tuple[PerformerServiceProfileDTO, ...]


@dataclass(frozen=True)
class FullAddressSnapshotDTO:
    city_name: str
    district_name: str | None
    address_text: str
    fias_id: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    geocoding_provider: str | None
    geocoding_quality: str | None
    entrance: str | None
    floor: str | None
    apartment: str | None
    comment: str | None


@dataclass(frozen=True)
class OrderLocationDTO:
    order_id: UUID
    city_name: str
    district_name: str | None
    address: FullAddressSnapshotDTO | None


@dataclass(frozen=True)
class PaymentPromptDTO:
    payment_id: UUID
    confirmation_url: str | None
    expires_at: datetime
    timezone: str


@dataclass(frozen=True)
class OrderMatchDTO:
    id: UUID
    order_id: UUID
    performer_id: UUID
    source: str
    status: str
    starts_at: datetime
    ends_at: datetime
    response_expires_at: datetime
    selected_at: datetime | None
    closed_at: datetime | None
    close_reason: str | None
    timezone: str
    service_name: str | None = None
    total_amount: Decimal | None = None
    distance_km: Decimal | None = None
    customer_comment: str | None = None


@dataclass(frozen=True)
class OrderReportDTO:
    id: UUID
    order_id: UUID
    performer_id: UUID
    completed_work: str
    comment: str | None
    problem_flag: bool
    problem_description: str | None
    submitted_at: datetime
    file_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class OrderReportFileDTO:
    id: UUID
    original_name: str | None
    mime_type: str
    signed_url: str


@dataclass(frozen=True)
class OrderReportDetailDTO:
    id: UUID
    order_id: UUID
    performer_id: UUID
    completed_work: str
    comment: str | None
    problem_flag: bool
    problem_description: str | None
    submitted_at: datetime
    files: tuple[OrderReportFileDTO, ...]


@dataclass(frozen=True)
class MatchActionDTO:
    order: OrderDTO
    match: OrderMatchDTO
    payment: PaymentPromptDTO | None


@dataclass(frozen=True)
class MyOrderSummaryDTO:
    id: UUID
    category_code: str
    service_name: str
    matching_mode: str | None
    status: str
    start_at: datetime
    end_at: datetime
    objects_count: int
    total_amount: Decimal
    payment_deadline_at: datetime | None
    matching_deadline_at: datetime
    timezone: str
    price_type: str = field(default="hourly", kw_only=True)


@dataclass(frozen=True)
class MyOrderCardDTO(MyOrderSummaryDTO):
    payment_status: str | None
    payment_confirmation_url: str | None
    payment_expires_at: datetime | None
    payment_attempts_used: int = 0
    payment_max_attempts: int = 3
    payment_retry_available: bool = False
    customer_comment: str | None = None


@dataclass(frozen=True)
class CancellationPreviewDTO:
    order_id: UUID
    order_status: str
    can_cancel: bool
    refund_outcome: str
    refund_amount: Decimal
    policy_version: str | None
    partial_refund_percent: Decimal | None
    remaining_minutes: int


@dataclass(frozen=True)
class MyOrdersPageDTO:
    items: tuple[MyOrderSummaryDTO, ...]
    page: int
    page_size: int
    total_items: int
    total_pages: int

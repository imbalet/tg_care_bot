from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class CityDTO:
    id: UUID
    name: str
    timezone: str = "Europe/Moscow"


@dataclass(frozen=True)
class LegalDocumentDTO:
    id: UUID
    document_type: str
    version: str
    content_url: str


@dataclass(frozen=True)
class ServiceOptionDTO:
    id: UUID
    code: str
    name: str
    value_type: str
    is_required: bool


@dataclass(frozen=True)
class ServiceDTO:
    id: UUID
    code: str
    name: str
    description: str
    price_type: str
    base_price: Decimal
    location_policy: str
    photo_policy: str
    schedule_policy: str
    allows_multiday: bool
    min_duration_minutes: int | None
    max_duration_minutes: int | None
    duration_step_minutes: int | None
    options: tuple[ServiceOptionDTO, ...]


@dataclass(frozen=True)
class ServiceCategoryDTO:
    id: UUID
    code: str
    name: str
    care_object_type: str
    max_objects_per_order: int
    services: tuple[ServiceDTO, ...]


@dataclass(frozen=True)
class CustomerProfileDTO:
    id: UUID
    telegram_id: int
    full_name: str
    phone: str
    telegram_username: str | None
    contact_method: str
    city_id: UUID
    status: str
    city_name: str = ""


@dataclass(frozen=True)
class CareObjectDTO:
    id: UUID
    object_type: str
    display_name: str
    age_group: str
    species: str | None
    breed: str | None
    pet_size: str | None
    mobility_assistance_required: bool | None
    routine_notes: str | None
    behavior_notes: str | None


@dataclass(frozen=True)
class AddressSuggestionDTO:
    value: str
    unrestricted_value: str


@dataclass(frozen=True)
class AddressDTO:
    id: UUID
    city_id: UUID
    address_text: str
    entrance: str | None
    floor: str | None
    apartment: str | None
    comment: str | None


@dataclass(frozen=True)
class PricePreviewDTO:
    service_id: UUID
    service_code: str
    service_name: str
    duration_minutes: int
    objects_count: int
    service_amount: Decimal
    platform_fee_amount: Decimal
    total_amount: Decimal


@dataclass(frozen=True)
class OrderDTO:
    id: UUID
    customer_id: UUID | None
    service_id: UUID
    service_name: str
    matching_mode: str | None
    status: str
    start_at: datetime
    end_at: datetime
    objects_count: int
    total_amount: Decimal


@dataclass(frozen=True)
class OrderMatchDTO:
    id: UUID
    order_id: UUID
    performer_id: UUID
    match_type: str
    status: str


@dataclass(frozen=True)
class MatchActionDTO:
    order_id: UUID
    order_status: str
    match_id: UUID
    payment_confirmation_url: str | None


@dataclass(frozen=True)
class PaymentStatusDTO:
    order_id: UUID
    order_status: str
    payment_id: UUID | None
    payment_status: str | None
    confirmation_url: str | None
    expires_at: datetime | None
    failure_code: str | None = None
    attempts_used: int = 0
    max_attempts: int = 3
    retry_available: bool = False


@dataclass(frozen=True)
class SupportContactDTO:
    label: str
    telegram_url: str | None


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


@dataclass(frozen=True)
class MyOrderCardDTO(MyOrderSummaryDTO):
    payment_status: str | None
    payment_confirmation_url: str | None
    payment_expires_at: datetime | None
    payment_attempts_used: int = 0
    payment_max_attempts: int = 3
    payment_retry_available: bool = False


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
class FullAddressSnapshotDTO:
    city_name: str
    district_name: str | None
    address_text: str
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
class OrderReportFileDTO:
    id: UUID
    original_name: str | None
    mime_type: str
    signed_url: str


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
    files: tuple[OrderReportFileDTO, ...]


@dataclass(frozen=True)
class SupportRecordDTO:
    id: UUID
    kind: str
    order_id: UUID | None
    status: str
    text: str | None
    category: str | None
    blockers: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class DeletionPreflightDTO:
    can_delete: bool
    blockers: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class ContactRequestDTO:
    id: UUID
    order_id: UUID
    performer_id: UUID
    requested_method: str
    status: str
    failure_reason: str | None
    contact_name: str
    contact_phone: str | None
    contact_telegram_username: str | None


@dataclass(frozen=True)
class PerformerServiceProfileDTO:
    service_id: UUID
    service_name: str
    price_type: str
    base_price: Decimal
    performer_max_objects: int


@dataclass(frozen=True)
class PerformerProfileDTO:
    performer_id: UUID
    full_name: str
    about_text: str | None
    city_name: str
    avatar_url: str | None
    services: tuple[PerformerServiceProfileDTO, ...]


@dataclass(frozen=True)
class MyOrdersPageDTO:
    items: tuple[MyOrderSummaryDTO, ...]
    page: int
    page_size: int
    total_items: int
    total_pages: int


@dataclass(frozen=True)
class SuitablePerformerDTO:
    performer_id: UUID
    full_name: str
    service_id: UUID
    service_name: str
    performer_max_objects: int
    distance_km: Decimal | None

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class CityDTO:
    id: UUID
    name: str


@dataclass(frozen=True)
class LegalDocumentDTO:
    id: UUID
    document_type: str
    version: str
    content_url: str


@dataclass(frozen=True)
class ServiceDTO:
    id: UUID
    code: str
    name: str
    description: str
    price_type: str
    base_price: str
    location_policy: str
    photo_policy: str
    schedule_policy: str
    allows_multiday: bool
    min_duration_minutes: int | None
    max_duration_minutes: int | None


@dataclass(frozen=True)
class ServiceCategoryDTO:
    id: UUID
    code: str
    name: str
    sort_order: int
    care_object_type: str
    services: tuple[ServiceDTO, ...]


@dataclass(frozen=True)
class PerformerProfileDTO:
    id: UUID
    telegram_id: int
    full_name: str
    phone: str
    telegram_username: str | None
    contact_method: str
    city_id: UUID
    about_text: str | None
    status: str
    is_accepting_orders: bool
    current_address_id: UUID | None


@dataclass(frozen=True)
class RegistrationStateDTO:
    state: str
    performer: PerformerProfileDTO | None


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
class FileDTO:
    id: UUID
    mime_type: str
    size_bytes: int | None
    status: str


@dataclass(frozen=True)
class DeletionPreflightDTO:
    can_delete: bool
    blockers: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class PerformerServiceDTO:
    service_id: UUID
    service_code: str
    service_name: str
    service_location_policy: str
    is_approved: bool
    is_enabled: bool
    admin_max_objects: int
    performer_max_objects: int
    constraints: dict[str, Any]


@dataclass(frozen=True)
class PerformerScheduleDTO:
    schedule_type: str
    work_days: tuple[int, ...] | None
    work_start_time: str
    work_end_time: str


@dataclass(frozen=True)
class CalendarOverrideDTO:
    id: UUID
    override_type: str
    starts_at: datetime
    ends_at: datetime
    comment: str | None
    timezone: str
    is_active: bool


@dataclass(frozen=True)
class BusyIntervalDTO:
    id: UUID
    kind: str
    status: str
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class CalendarDTO:
    schedule: PerformerScheduleDTO | None
    overrides: tuple[CalendarOverrideDTO, ...]
    busy_intervals: tuple[BusyIntervalDTO, ...]


@dataclass(frozen=True)
class AvailableOrderDTO:
    id: UUID
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
    source: str
    status: str
    starts_at: datetime
    ends_at: datetime
    response_expires_at: datetime
    selected_at: datetime | None
    closed_at: datetime | None
    close_reason: str | None
    timezone: str


@dataclass(frozen=True)
class MatchActionDTO:
    order_id: UUID
    match_id: UUID
    status: str
    confirmation_url: str | None


@dataclass(frozen=True)
class SupportContactDTO:
    label: str
    telegram_url: str | None


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
class OrderLocationDTO:
    order_id: UUID
    city_name: str
    district_name: str | None
    address_text: str | None
    entrance: str | None
    floor: str | None
    apartment: str | None
    comment: str | None


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
class MyOrderSummaryDTO:
    id: UUID
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
    payment_expires_at: datetime | None


@dataclass(frozen=True)
class MyOrdersPageDTO:
    items: tuple[MyOrderSummaryDTO, ...]
    page: int
    page_size: int
    total_items: int
    total_pages: int


__all__ = [
    "AddressDTO",
    "AddressSuggestionDTO",
    "AvailableOrderDTO",
    "CityDTO",
    "ContactRequestDTO",
    "FileDTO",
    "LegalDocumentDTO",
    "MatchActionDTO",
    "MyOrderCardDTO",
    "MyOrderSummaryDTO",
    "MyOrdersPageDTO",
    "OrderMatchDTO",
    "OrderLocationDTO",
    "OrderReportDTO",
    "OrderReportFileDTO",
    "PerformerProfileDTO",
    "PerformerScheduleDTO",
    "PerformerServiceDTO",
    "RegistrationStateDTO",
    "ServiceCategoryDTO",
    "ServiceDTO",
    "SupportContactDTO",
]

from dataclasses import dataclass
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


__all__ = [
    "AddressDTO",
    "AddressSuggestionDTO",
    "CityDTO",
    "FileDTO",
    "LegalDocumentDTO",
    "PerformerProfileDTO",
    "PerformerScheduleDTO",
    "PerformerServiceDTO",
    "RegistrationStateDTO",
    "ServiceCategoryDTO",
    "ServiceDTO",
]

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class CityDTO:
    id: UUID
    name: str
    slug: str
    timezone: str
    is_active: bool


@dataclass(frozen=True)
class LegalDocumentDTO:
    id: UUID
    document_type: str
    version: str
    content_url: str
    is_active: bool
    published_at: datetime


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
    is_active: bool
    sort_order: int


@dataclass(frozen=True)
class ServiceCategoryDTO:
    id: UUID
    code: str
    name: str
    care_object_type: str
    max_objects_per_order: int
    is_active: bool
    sort_order: int
    services: tuple[ServiceDTO, ...]


@dataclass(frozen=True)
class CatalogDTO:
    categories: tuple[ServiceCategoryDTO, ...]

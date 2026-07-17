from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class AddressDTO:
    id: UUID
    owner_type: str
    customer_id: UUID | None
    performer_id: UUID | None
    city_id: UUID
    district_id: UUID | None
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
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class CreateAddressCommand:
    owner_type: str
    customer_id: UUID | None
    performer_id: UUID | None
    city_id: UUID
    district_id: UUID | None
    address_text: str
    fias_id: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    geocoding_provider: str | None
    geocoding_quality: str | None
    entrance: str | None = None
    floor: str | None = None
    apartment: str | None = None
    comment: str | None = None

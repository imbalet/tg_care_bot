from uuid import UUID

from pydantic import BaseModel, Field


class RegisterCustomerRequest(BaseModel):
    telegram_id: int
    full_name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    city_id: UUID
    contact_method: str
    telegram_username: str | None = None
    accepted_legal_document_ids: list[UUID]


class UpdateTelegramUsernameRequest(BaseModel):
    telegram_username: str | None = None


class UpdateCustomerProfileRequest(BaseModel):
    full_name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    city_id: UUID
    contact_method: str


class CustomerResponse(BaseModel):
    id: str
    telegram_id: int
    full_name: str
    phone: str
    telegram_username: str | None
    contact_method: str
    city_id: str
    status: str


class CareObjectRequest(BaseModel):
    display_name: str = Field(min_length=1)
    age_group: str
    species: str | None = None
    breed: str | None = None
    pet_size: str | None = None
    mobility_assistance_required: bool | None = None
    routine_notes: str | None = None
    behavior_notes: str | None = None


class CreateCareObjectRequest(CareObjectRequest):
    object_type: str


class CareObjectResponse(BaseModel):
    id: str
    customer_id: str
    object_type: str
    display_name: str
    age_group: str
    species: str | None
    breed: str | None
    pet_size: str | None
    mobility_assistance_required: bool | None
    routine_notes: str | None
    behavior_notes: str | None
    deleted_at: str | None
    created_at: str
    updated_at: str


class CreateAddressRequest(BaseModel):
    city_id: UUID
    unrestricted_value: str = Field(min_length=1)
    entrance: str | None = None
    floor: str | None = None
    apartment: str | None = None
    comment: str | None = None


class UpdateAddressRequest(CreateAddressRequest):
    pass


class AddressResponse(BaseModel):
    id: str
    owner_type: str
    customer_id: str | None
    performer_id: str | None
    city_id: str
    district_id: str | None
    address_text: str
    fias_id: str | None
    latitude: str | None
    longitude: str | None
    geocoding_provider: str | None
    geocoding_quality: str | None
    entrance: str | None
    floor: str | None
    apartment: str | None
    comment: str | None
    deleted_at: str | None
    created_at: str
    updated_at: str

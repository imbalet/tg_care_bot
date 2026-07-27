from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CreateInvitationRequest(BaseModel):
    telegram_id: int
    created_by_admin_id: UUID
    expires_at: datetime | None = None


class CreateAdminInvitationRequest(BaseModel):
    telegram_id: int
    expires_at: datetime | None = None


class RegisterPerformerRequest(BaseModel):
    telegram_id: int
    full_name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    city_id: UUID
    contact_method: str
    about_text: str = Field(min_length=1)
    telegram_username: str | None = None
    accepted_legal_document_ids: list[UUID]


class UpdateTelegramUsernameRequest(BaseModel):
    telegram_username: str | None = None


class UpdatePerformerProfileRequest(BaseModel):
    phone: str = Field(min_length=1)
    contact_method: str


class ApprovePerformerServiceRequest(BaseModel):
    admin_max_objects: int = Field(ge=1)
    constraints: dict[str, Any] = Field(default_factory=dict)


class SetPerformerServiceEnabledRequest(BaseModel):
    is_enabled: bool


class SetPerformerServiceMaxObjectsRequest(BaseModel):
    performer_max_objects: int = Field(ge=1)


class SetAcceptingOrdersRequest(BaseModel):
    is_accepting_orders: bool


class SetNearbyOrderNotificationsRequest(BaseModel):
    is_enabled: bool


class NearbyOrderNotificationsResponse(BaseModel):
    is_enabled: bool


class CreateAddressRequest(BaseModel):
    city_id: UUID
    unrestricted_value: str = Field(min_length=1)
    entrance: str | None = None
    floor: str | None = None
    apartment: str | None = None
    comment: str | None = None


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


class FileResponse(BaseModel):
    id: str
    bucket: str
    storage_key: str | None
    mime_type: str
    size_bytes: int | None
    checksum: str | None
    status: str


class InvitationResponse(BaseModel):
    id: str
    telegram_id: int
    status: str
    expires_at: str | None
    accepted_performer_id: str | None


class PerformerResponse(BaseModel):
    id: str
    telegram_id: int
    full_name: str
    phone: str
    telegram_username: str | None
    contact_method: str
    city_id: str
    about_text: str | None
    status: str
    is_accepting_orders: bool
    current_address_id: str | None


class PerformerServiceResponse(BaseModel):
    id: str
    performer_id: str
    service_id: str
    service_code: str
    service_name: str
    service_location_policy: str
    is_approved: bool
    is_enabled: bool
    admin_max_objects: int
    performer_max_objects: int
    constraints: dict[str, Any]
    approved_by_admin_id: str | None
    approved_at: str | None


class RegistrationStateResponse(BaseModel):
    state: str
    invitation: InvitationResponse | None
    performer: PerformerResponse | None

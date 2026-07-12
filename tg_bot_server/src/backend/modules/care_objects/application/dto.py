from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CareObjectDTO:
    id: UUID
    customer_id: UUID
    object_type: str
    display_name: str
    age_group: str
    species: str | None
    breed: str | None
    pet_size: str | None
    mobility_assistance_required: bool | None
    routine_notes: str | None
    behavior_notes: str | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class CreateCareObjectCommand:
    customer_id: UUID
    object_type: str
    display_name: str
    age_group: str
    species: str | None = None
    breed: str | None = None
    pet_size: str | None = None
    mobility_assistance_required: bool | None = None
    routine_notes: str | None = None
    behavior_notes: str | None = None


@dataclass(frozen=True)
class UpdateCareObjectCommand:
    care_object_id: UUID
    display_name: str
    age_group: str
    species: str | None = None
    breed: str | None = None
    pet_size: str | None = None
    mobility_assistance_required: bool | None = None
    routine_notes: str | None = None
    behavior_notes: str | None = None


__all__ = ["CareObjectDTO", "CreateCareObjectCommand", "UpdateCareObjectCommand"]

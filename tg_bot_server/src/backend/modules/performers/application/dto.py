from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class InvitationDTO:
    id: UUID
    telegram_id: int
    status: str
    expires_at: datetime | None
    accepted_performer_id: UUID | None
    updated_at: datetime


@dataclass(frozen=True)
class PerformerDTO:
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
    invitation: InvitationDTO | None
    performer: PerformerDTO | None


@dataclass(frozen=True)
class PerformerServiceDTO:
    id: UUID
    performer_id: UUID
    service_id: UUID
    service_code: str
    service_name: str
    service_location_policy: str
    is_approved: bool
    is_enabled: bool
    admin_max_objects: int
    performer_max_objects: int
    constraints: dict[str, Any]
    approved_by_admin_id: UUID | None
    approved_at: datetime | None


@dataclass(frozen=True)
class PerformerServiceSelection:
    service_id: UUID
    admin_max_objects: int
    constraints: dict[str, Any]


@dataclass(frozen=True)
class PerformerServicesSyncResult:
    services: tuple[PerformerServiceDTO, ...]
    added: tuple[PerformerServiceDTO, ...]
    revoked: tuple[PerformerServiceDTO, ...]
    updated: tuple[PerformerServiceDTO, ...]

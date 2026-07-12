from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class InvitationDTO:
    id: UUID
    telegram_id: int
    status: str
    expires_at: datetime | None
    accepted_performer_id: UUID | None


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


@dataclass(frozen=True)
class RegistrationStateDTO:
    state: str
    invitation: InvitationDTO | None
    performer: PerformerDTO | None


__all__ = ["InvitationDTO", "PerformerDTO", "RegistrationStateDTO"]

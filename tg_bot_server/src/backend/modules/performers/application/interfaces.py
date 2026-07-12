from datetime import datetime
from typing import Protocol
from uuid import UUID

from backend.modules.performers.application.dto import InvitationDTO, PerformerDTO


class PerformerRepository(Protocol):
    async def create_invitation(
        self,
        *,
        telegram_id: int,
        created_by_admin_id: UUID,
        expires_at: datetime | None,
    ) -> InvitationDTO:
        pass

    async def get_performer_by_telegram_id(
        self,
        telegram_id: int,
    ) -> PerformerDTO | None:
        pass

    async def get_pending_invitation(self, telegram_id: int) -> InvitationDTO | None:
        pass

    async def mark_invitation_expired(self, invitation_id: UUID) -> None:
        pass

    async def create_performer_from_invitation(
        self,
        *,
        invitation_id: UUID,
        telegram_id: int,
        full_name: str,
        phone: str,
        city_id: UUID,
        contact_method: str,
        about_text: str,
        telegram_username: str | None,
        accepted_legal_document_ids: tuple[UUID, ...],
    ) -> PerformerDTO:
        pass

    async def activate(self, performer_id: UUID) -> PerformerDTO | None:
        pass

    async def update_username(
        self,
        *,
        telegram_id: int,
        telegram_username: str | None,
    ) -> PerformerDTO | None:
        pass

    async def get_city_is_active(self, city_id: UUID) -> bool:
        pass

    async def list_active_legal_document_ids(self) -> tuple[UUID, ...]:
        pass


__all__ = ["PerformerRepository"]

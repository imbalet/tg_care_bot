from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from backend.common.application import Clock, SystemClock
from backend.common.domain import NotFoundError, ValidationError
from backend.modules.performers.application.dto import (
    InvitationDTO,
    PerformerDTO,
    RegistrationStateDTO,
)
from backend.modules.performers.application.interfaces import PerformerRepository


@dataclass(frozen=True)
class CreateInvitationCommand:
    telegram_id: int
    created_by_admin_id: UUID
    expires_at: datetime | None


class CreateInvitationUseCase:
    def __init__(self, repository: PerformerRepository) -> None:
        self._repository = repository

    async def execute(self, command: CreateInvitationCommand) -> InvitationDTO:
        return await self._repository.create_invitation(
            telegram_id=command.telegram_id,
            created_by_admin_id=command.created_by_admin_id,
            expires_at=command.expires_at,
        )


class GetRegistrationStateUseCase:
    def __init__(
        self,
        repository: PerformerRepository,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or SystemClock()

    async def execute(self, telegram_id: int) -> RegistrationStateDTO:
        performer = await self._repository.get_performer_by_telegram_id(telegram_id)
        if performer is not None:
            return RegistrationStateDTO(
                state="registered",
                invitation=None,
                performer=performer,
            )
        invitation = await self._repository.get_pending_invitation(telegram_id)
        if invitation is None:
            return RegistrationStateDTO(
                state="no_invitation",
                invitation=None,
                performer=None,
            )
        if (
            invitation.expires_at is not None
            and invitation.expires_at <= self._clock.now()
        ):
            await self._repository.mark_invitation_expired(invitation.id)
            return RegistrationStateDTO(
                state="no_invitation",
                invitation=None,
                performer=None,
            )
        return RegistrationStateDTO(
            state="invited",
            invitation=invitation,
            performer=None,
        )


@dataclass(frozen=True)
class RegisterPerformerCommand:
    telegram_id: int
    full_name: str
    phone: str
    city_id: UUID
    contact_method: str
    about_text: str
    telegram_username: str | None
    accepted_legal_document_ids: tuple[UUID, ...]


class RegisterPerformerUseCase:
    def __init__(
        self,
        repository: PerformerRepository,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or SystemClock()

    async def execute(self, command: RegisterPerformerCommand) -> PerformerDTO:
        existing = await self._repository.get_performer_by_telegram_id(
            command.telegram_id,
        )
        if existing is not None:
            return existing
        if command.contact_method not in {"telegram", "phone", "both"}:
            raise ValidationError("Contact method is invalid")
        if not await self._repository.get_city_is_active(command.city_id):
            raise ValidationError("City is inactive or unknown")
        required_documents = set(
            await self._repository.list_active_legal_document_ids()
        )
        if not required_documents.issubset(set(command.accepted_legal_document_ids)):
            raise ValidationError("Required legal documents are not accepted")
        invitation = await self._repository.get_pending_invitation(command.telegram_id)
        if invitation is None:
            raise ValidationError("Invitation is required")
        if (
            invitation.expires_at is not None
            and invitation.expires_at <= self._clock.now()
        ):
            await self._repository.mark_invitation_expired(invitation.id)
            raise ValidationError("Invitation is expired")
        return await self._repository.create_performer_from_invitation(
            invitation_id=invitation.id,
            telegram_id=command.telegram_id,
            full_name=command.full_name,
            phone=command.phone,
            city_id=command.city_id,
            contact_method=command.contact_method,
            about_text=command.about_text,
            telegram_username=command.telegram_username,
            accepted_legal_document_ids=command.accepted_legal_document_ids,
        )


class ActivatePerformerUseCase:
    def __init__(self, repository: PerformerRepository) -> None:
        self._repository = repository

    async def execute(self, performer_id: UUID) -> PerformerDTO:
        performer = await self._repository.activate(performer_id)
        if performer is None:
            raise NotFoundError("Performer not found")
        return performer


__all__ = [
    "ActivatePerformerUseCase",
    "CreateInvitationCommand",
    "CreateInvitationUseCase",
    "GetRegistrationStateUseCase",
    "RegisterPerformerCommand",
    "RegisterPerformerUseCase",
]

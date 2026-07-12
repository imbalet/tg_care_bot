from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from backend.common.application import Clock, SystemClock
from backend.common.domain import NotFoundError, ValidationError
from backend.modules.performers.application.dto import (
    InvitationDTO,
    PerformerDTO,
    PerformerServiceDTO,
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


@dataclass(frozen=True)
class UpdatePerformerUsernameCommand:
    telegram_id: int
    telegram_username: str | None


class UpdatePerformerUsernameUseCase:
    def __init__(self, repository: PerformerRepository) -> None:
        self._repository = repository

    async def execute(self, command: UpdatePerformerUsernameCommand) -> PerformerDTO:
        performer = await self._repository.update_username(
            telegram_id=command.telegram_id,
            telegram_username=command.telegram_username,
        )
        if performer is None:
            raise NotFoundError("Performer not found")
        return performer


@dataclass(frozen=True)
class ApprovePerformerServiceCommand:
    performer_id: UUID
    service_id: UUID
    admin_max_objects: int
    constraints: dict[str, Any]
    approved_by_admin_id: UUID


class ApprovePerformerServiceUseCase:
    def __init__(self, repository: PerformerRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        command: ApprovePerformerServiceCommand,
    ) -> PerformerServiceDTO:
        if command.admin_max_objects < 1:
            raise ValidationError("Admin max objects must be positive")
        service_order_limit = await self._repository.get_service_order_limit(
            command.service_id,
        )
        if service_order_limit is None:
            raise NotFoundError("Service not found")
        if command.admin_max_objects > service_order_limit:
            raise ValidationError("Admin max objects exceeds service order limit")
        service = await self._repository.approve_service(
            performer_id=command.performer_id,
            service_id=command.service_id,
            admin_max_objects=command.admin_max_objects,
            constraints=command.constraints,
            approved_by_admin_id=command.approved_by_admin_id,
        )
        if service is None:
            raise NotFoundError("Performer not found")
        return service


class ListPerformerServicesUseCase:
    def __init__(self, repository: PerformerRepository) -> None:
        self._repository = repository

    async def execute_for_performer(
        self,
        performer_id: UUID,
    ) -> tuple[PerformerServiceDTO, ...]:
        return await self._repository.list_services_for_performer(performer_id)

    async def execute_by_telegram_id(
        self,
        telegram_id: int,
    ) -> tuple[PerformerServiceDTO, ...]:
        services = await self._repository.list_services_by_telegram_id(telegram_id)
        if services is None:
            raise NotFoundError("Performer not found")
        return services


@dataclass(frozen=True)
class SetPerformerServiceEnabledCommand:
    telegram_id: int
    service_id: UUID
    is_enabled: bool


class SetPerformerServiceEnabledUseCase:
    def __init__(self, repository: PerformerRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        command: SetPerformerServiceEnabledCommand,
    ) -> PerformerServiceDTO:
        performer = await self._repository.get_performer_by_telegram_id(
            command.telegram_id,
        )
        if performer is None:
            raise NotFoundError("Performer not found")
        service = await self._find_service(command.telegram_id, command.service_id)
        if command.is_enabled:
            if not service.is_approved:
                raise ValidationError("Service is not approved")
            if (
                service.service_location_policy == "performer_address"
                and performer.current_address_id is None
            ):
                raise ValidationError("Current performer address is required")
        return await self._set_enabled(command)

    async def _find_service(
        self,
        telegram_id: int,
        service_id: UUID,
    ) -> PerformerServiceDTO:
        services = await self._repository.list_services_by_telegram_id(telegram_id)
        if services is None:
            raise NotFoundError("Performer not found")
        for service in services:
            if service.service_id == service_id:
                return service
        raise NotFoundError("Approved performer service not found")

    async def _set_enabled(
        self,
        command: SetPerformerServiceEnabledCommand,
    ) -> PerformerServiceDTO:
        service = await self._repository.set_service_enabled_by_telegram_id(
            telegram_id=command.telegram_id,
            service_id=command.service_id,
            is_enabled=command.is_enabled,
        )
        if service is None:
            raise NotFoundError("Approved performer service not found")
        return service


@dataclass(frozen=True)
class SetPerformerServiceMaxObjectsCommand:
    telegram_id: int
    service_id: UUID
    performer_max_objects: int


class SetPerformerServiceMaxObjectsUseCase:
    def __init__(self, repository: PerformerRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        command: SetPerformerServiceMaxObjectsCommand,
    ) -> PerformerServiceDTO:
        if command.performer_max_objects < 1:
            raise ValidationError("Performer max objects must be positive")
        services = await self._repository.list_services_by_telegram_id(
            command.telegram_id,
        )
        if services is None:
            raise NotFoundError("Performer not found")
        current = next(
            (
                service
                for service in services
                if service.service_id == command.service_id
            ),
            None,
        )
        if current is None:
            raise NotFoundError("Approved performer service not found")
        if command.performer_max_objects > current.admin_max_objects:
            raise ValidationError("Performer max objects exceeds admin limit")
        service = await self._repository.set_service_max_objects_by_telegram_id(
            telegram_id=command.telegram_id,
            service_id=command.service_id,
            performer_max_objects=command.performer_max_objects,
        )
        if service is None:
            raise NotFoundError("Approved performer service not found")
        return service


@dataclass(frozen=True)
class SetPerformerAcceptingOrdersCommand:
    telegram_id: int
    is_accepting_orders: bool


class SetPerformerAcceptingOrdersUseCase:
    def __init__(self, repository: PerformerRepository) -> None:
        self._repository = repository

    async def execute(
        self, command: SetPerformerAcceptingOrdersCommand
    ) -> PerformerDTO:
        performer = await self._repository.set_accepting_orders_by_telegram_id(
            telegram_id=command.telegram_id,
            is_accepting_orders=command.is_accepting_orders,
        )
        if performer is None:
            raise NotFoundError("Active performer not found")
        return performer


__all__ = [
    "ActivatePerformerUseCase",
    "ApprovePerformerServiceCommand",
    "ApprovePerformerServiceUseCase",
    "CreateInvitationCommand",
    "CreateInvitationUseCase",
    "GetRegistrationStateUseCase",
    "ListPerformerServicesUseCase",
    "RegisterPerformerCommand",
    "RegisterPerformerUseCase",
    "SetPerformerAcceptingOrdersCommand",
    "SetPerformerAcceptingOrdersUseCase",
    "SetPerformerServiceEnabledCommand",
    "SetPerformerServiceEnabledUseCase",
    "SetPerformerServiceMaxObjectsCommand",
    "SetPerformerServiceMaxObjectsUseCase",
    "UpdatePerformerUsernameCommand",
    "UpdatePerformerUsernameUseCase",
]

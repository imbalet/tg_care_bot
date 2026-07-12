from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from backend.common.domain import NotFoundError, ValidationError
from backend.modules.performers.application import (
    ApprovePerformerServiceCommand,
    ApprovePerformerServiceUseCase,
    CreateInvitationCommand,
    CreateInvitationUseCase,
    GetRegistrationStateUseCase,
    InvitationDTO,
    PerformerDTO,
    PerformerServiceDTO,
    RegisterPerformerCommand,
    RegisterPerformerUseCase,
    SetPerformerAcceptingOrdersCommand,
    SetPerformerAcceptingOrdersUseCase,
    SetPerformerServiceEnabledCommand,
    SetPerformerServiceEnabledUseCase,
    SetPerformerServiceMaxObjectsCommand,
    SetPerformerServiceMaxObjectsUseCase,
    UpdatePerformerUsernameCommand,
    UpdatePerformerUsernameUseCase,
)


class FakePerformerRepository:
    def __init__(self) -> None:
        self.invitations: dict[int, InvitationDTO] = {}
        self.performers: dict[int, PerformerDTO] = {}
        self.performer_services: dict[tuple[UUID, UUID], PerformerServiceDTO] = {}
        self.service_order_limits: dict[UUID, int] = {}
        self.service_location_policies: dict[UUID, str] = {}
        self.active_city_ids: set[UUID] = set()
        self.active_document_ids: tuple[UUID, ...] = ()

    async def create_invitation(
        self,
        *,
        telegram_id: int,
        created_by_admin_id: UUID,
        expires_at: datetime | None,
    ) -> InvitationDTO:
        invitation = InvitationDTO(
            id=uuid4(),
            telegram_id=telegram_id,
            status="pending",
            expires_at=expires_at,
            accepted_performer_id=None,
        )
        self.invitations[telegram_id] = invitation
        return invitation

    async def get_performer_by_telegram_id(
        self,
        telegram_id: int,
    ) -> PerformerDTO | None:
        return self.performers.get(telegram_id)

    async def get_pending_invitation(self, telegram_id: int) -> InvitationDTO | None:
        invitation = self.invitations.get(telegram_id)
        if invitation is None or invitation.status != "pending":
            return None
        return invitation

    async def mark_invitation_expired(self, invitation_id: UUID) -> None:
        for telegram_id, invitation in self.invitations.items():
            if invitation.id == invitation_id:
                self.invitations[telegram_id] = InvitationDTO(
                    id=invitation.id,
                    telegram_id=invitation.telegram_id,
                    status="expired",
                    expires_at=invitation.expires_at,
                    accepted_performer_id=None,
                )

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
        performer = PerformerDTO(
            id=uuid4(),
            telegram_id=telegram_id,
            full_name=full_name,
            phone=phone,
            telegram_username=telegram_username,
            contact_method=contact_method,
            city_id=city_id,
            about_text=about_text,
            status="profile_pending",
            is_accepting_orders=False,
            current_address_id=None,
        )
        self.performers[telegram_id] = performer
        return performer

    async def activate(self, performer_id: UUID) -> PerformerDTO | None:
        for telegram_id, performer in self.performers.items():
            if performer.id == performer_id:
                active = PerformerDTO(**{**performer.__dict__, "status": "active"})
                self.performers[telegram_id] = active
                return active
        return None

    async def update_username(
        self,
        *,
        telegram_id: int,
        telegram_username: str | None,
    ) -> PerformerDTO | None:
        performer = self.performers.get(telegram_id)
        if performer is None:
            return None
        updated = PerformerDTO(
            **{**performer.__dict__, "telegram_username": telegram_username},
        )
        self.performers[telegram_id] = updated
        return updated

    async def set_current_address(
        self,
        *,
        performer_id: UUID,
        address_id: UUID,
    ) -> None:
        for telegram_id, performer in self.performers.items():
            if performer.id == performer_id:
                self.performers[telegram_id] = PerformerDTO(
                    **{**performer.__dict__, "current_address_id": address_id},
                )
                return

    async def get_city_is_active(self, city_id: UUID) -> bool:
        return city_id in self.active_city_ids

    async def list_active_legal_document_ids(self) -> tuple[UUID, ...]:
        return self.active_document_ids

    async def list_services_for_performer(
        self,
        performer_id: UUID,
    ) -> tuple[PerformerServiceDTO, ...]:
        return tuple(
            service
            for (current_performer_id, _service_id), service in (
                self.performer_services.items()
            )
            if current_performer_id == performer_id
        )

    async def list_services_by_telegram_id(
        self,
        telegram_id: int,
    ) -> tuple[PerformerServiceDTO, ...] | None:
        performer = self.performers.get(telegram_id)
        if performer is None:
            return None
        return await self.list_services_for_performer(performer.id)

    async def approve_service(
        self,
        *,
        performer_id: UUID,
        service_id: UUID,
        admin_max_objects: int,
        constraints: dict[str, object],
        approved_by_admin_id: UUID,
    ) -> PerformerServiceDTO | None:
        if not any(
            performer.id == performer_id for performer in self.performers.values()
        ):
            return None
        key = (performer_id, service_id)
        existing = self.performer_services.get(key)
        performer_max_objects = min(
            existing.performer_max_objects
            if existing is not None
            else admin_max_objects,
            admin_max_objects,
        )
        service = PerformerServiceDTO(
            id=existing.id if existing is not None else uuid4(),
            performer_id=performer_id,
            service_id=service_id,
            service_code="pet_boarding",
            service_name="Передержка",
            service_location_policy=self.service_location_policies.get(
                service_id,
                "customer_address",
            ),
            is_approved=True,
            is_enabled=existing.is_enabled if existing is not None else False,
            admin_max_objects=admin_max_objects,
            performer_max_objects=performer_max_objects,
            constraints=constraints,
            approved_by_admin_id=approved_by_admin_id,
            approved_at=datetime.now(UTC),
        )
        self.performer_services[key] = service
        return service

    async def set_service_enabled_by_telegram_id(
        self,
        *,
        telegram_id: int,
        service_id: UUID,
        is_enabled: bool,
    ) -> PerformerServiceDTO | None:
        performer = self.performers.get(telegram_id)
        if performer is None:
            return None
        service = self.performer_services.get((performer.id, service_id))
        if service is None or not service.is_approved:
            return None
        updated = PerformerServiceDTO(**{**service.__dict__, "is_enabled": is_enabled})
        self.performer_services[(performer.id, service_id)] = updated
        return updated

    async def set_service_max_objects_by_telegram_id(
        self,
        *,
        telegram_id: int,
        service_id: UUID,
        performer_max_objects: int,
    ) -> PerformerServiceDTO | None:
        performer = self.performers.get(telegram_id)
        if performer is None:
            return None
        service = self.performer_services.get((performer.id, service_id))
        if service is None or not service.is_approved:
            return None
        updated = PerformerServiceDTO(
            **{**service.__dict__, "performer_max_objects": performer_max_objects},
        )
        self.performer_services[(performer.id, service_id)] = updated
        return updated

    async def set_accepting_orders_by_telegram_id(
        self,
        *,
        telegram_id: int,
        is_accepting_orders: bool,
    ) -> PerformerDTO | None:
        performer = self.performers.get(telegram_id)
        if performer is None or performer.status != "active":
            return None
        updated = PerformerDTO(
            **{**performer.__dict__, "is_accepting_orders": is_accepting_orders},
        )
        self.performers[telegram_id] = updated
        return updated

    async def get_service_order_limit(self, service_id: UUID) -> int | None:
        return self.service_order_limits.get(service_id)


def make_repository() -> tuple[FakePerformerRepository, UUID, tuple[UUID, ...]]:
    repository = FakePerformerRepository()
    city_id = uuid4()
    documents = (uuid4(), uuid4())
    repository.active_city_ids.add(city_id)
    repository.active_document_ids = documents
    return repository, city_id, documents


def make_register_command(
    city_id: UUID,
    documents: tuple[UUID, ...],
) -> RegisterPerformerCommand:
    return RegisterPerformerCommand(
        telegram_id=123,
        full_name="Performer User",
        phone="+79990000000",
        city_id=city_id,
        contact_method="both",
        about_text="About performer",
        telegram_username="performer",
        accepted_legal_document_ids=documents,
    )


@pytest.mark.asyncio
async def test_invited_performer_registers_as_profile_pending() -> None:
    repository, city_id, documents = make_repository()
    await CreateInvitationUseCase(repository).execute(
        CreateInvitationCommand(
            telegram_id=123,
            created_by_admin_id=uuid4(),
            expires_at=None,
        ),
    )

    performer = await RegisterPerformerUseCase(repository).execute(
        make_register_command(city_id, documents),
    )

    assert performer.status == "profile_pending"
    assert performer.is_accepting_orders is False


@pytest.mark.asyncio
async def test_no_invitation_is_rejected() -> None:
    repository, city_id, documents = make_repository()

    with pytest.raises(ValidationError):
        await RegisterPerformerUseCase(repository).execute(
            make_register_command(city_id, documents),
        )


@pytest.mark.asyncio
async def test_expired_invitation_is_rejected() -> None:
    repository, city_id, documents = make_repository()
    await CreateInvitationUseCase(repository).execute(
        CreateInvitationCommand(
            telegram_id=123,
            created_by_admin_id=uuid4(),
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        ),
    )

    with pytest.raises(ValidationError):
        await RegisterPerformerUseCase(repository).execute(
            make_register_command(city_id, documents),
        )

    state = await GetRegistrationStateUseCase(repository).execute(123)
    assert state.state == "no_invitation"


@pytest.mark.asyncio
async def test_repeated_registration_returns_existing_performer() -> None:
    repository, city_id, documents = make_repository()
    await CreateInvitationUseCase(repository).execute(
        CreateInvitationCommand(
            telegram_id=123, created_by_admin_id=uuid4(), expires_at=None
        ),
    )
    use_case = RegisterPerformerUseCase(repository)

    first = await use_case.execute(make_register_command(city_id, documents))
    second = await use_case.execute(make_register_command(city_id, documents))

    assert second.id == first.id


@pytest.mark.asyncio
async def test_update_performer_username_to_value_and_null() -> None:
    repository, city_id, documents = make_repository()
    await CreateInvitationUseCase(repository).execute(
        CreateInvitationCommand(
            telegram_id=123,
            created_by_admin_id=uuid4(),
            expires_at=None,
        ),
    )
    performer = await RegisterPerformerUseCase(repository).execute(
        make_register_command(city_id, documents),
    )
    use_case = UpdatePerformerUsernameUseCase(repository)

    with_value = await use_case.execute(
        UpdatePerformerUsernameCommand(
            telegram_id=performer.telegram_id,
            telegram_username="new_name",
        ),
    )
    without_value = await use_case.execute(
        UpdatePerformerUsernameCommand(
            telegram_id=performer.telegram_id,
            telegram_username=None,
        ),
    )

    assert with_value.telegram_username == "new_name"
    assert without_value.telegram_username is None


@pytest.mark.asyncio
async def test_admin_approves_performer_service_with_limit_cap() -> None:
    repository, city_id, documents = make_repository()
    service_id = uuid4()
    repository.service_order_limits[service_id] = 2
    await CreateInvitationUseCase(repository).execute(
        CreateInvitationCommand(
            telegram_id=123,
            created_by_admin_id=uuid4(),
            expires_at=None,
        ),
    )
    performer = await RegisterPerformerUseCase(repository).execute(
        make_register_command(city_id, documents),
    )

    service = await ApprovePerformerServiceUseCase(repository).execute(
        ApprovePerformerServiceCommand(
            performer_id=performer.id,
            service_id=service_id,
            admin_max_objects=2,
            constraints={"accepted_pet_sizes": ["small"]},
            approved_by_admin_id=uuid4(),
        ),
    )

    assert service.is_approved is True
    assert service.admin_max_objects == 2

    with pytest.raises(ValidationError):
        await ApprovePerformerServiceUseCase(repository).execute(
            ApprovePerformerServiceCommand(
                performer_id=performer.id,
                service_id=service_id,
                admin_max_objects=3,
                constraints={},
                approved_by_admin_id=uuid4(),
            ),
        )


@pytest.mark.asyncio
async def test_performer_can_only_reduce_own_service_limit() -> None:
    repository, city_id, documents = make_repository()
    service_id = uuid4()
    repository.service_order_limits[service_id] = 3
    await CreateInvitationUseCase(repository).execute(
        CreateInvitationCommand(
            telegram_id=123,
            created_by_admin_id=uuid4(),
            expires_at=None,
        ),
    )
    performer = await RegisterPerformerUseCase(repository).execute(
        make_register_command(city_id, documents),
    )
    await ApprovePerformerServiceUseCase(repository).execute(
        ApprovePerformerServiceCommand(
            performer_id=performer.id,
            service_id=service_id,
            admin_max_objects=3,
            constraints={},
            approved_by_admin_id=uuid4(),
        ),
    )

    reduced = await SetPerformerServiceMaxObjectsUseCase(repository).execute(
        SetPerformerServiceMaxObjectsCommand(
            telegram_id=performer.telegram_id,
            service_id=service_id,
            performer_max_objects=2,
        ),
    )

    assert reduced.performer_max_objects == 2

    with pytest.raises(ValidationError):
        await SetPerformerServiceMaxObjectsUseCase(repository).execute(
            SetPerformerServiceMaxObjectsCommand(
                telegram_id=performer.telegram_id,
                service_id=service_id,
                performer_max_objects=4,
            ),
        )


@pytest.mark.asyncio
async def test_boarding_service_requires_current_address_to_enable() -> None:
    repository, city_id, documents = make_repository()
    service_id = uuid4()
    repository.service_order_limits[service_id] = 3
    repository.service_location_policies[service_id] = "performer_address"
    await CreateInvitationUseCase(repository).execute(
        CreateInvitationCommand(
            telegram_id=123,
            created_by_admin_id=uuid4(),
            expires_at=None,
        ),
    )
    performer = await RegisterPerformerUseCase(repository).execute(
        make_register_command(city_id, documents),
    )
    await ApprovePerformerServiceUseCase(repository).execute(
        ApprovePerformerServiceCommand(
            performer_id=performer.id,
            service_id=service_id,
            admin_max_objects=3,
            constraints={},
            approved_by_admin_id=uuid4(),
        ),
    )

    with pytest.raises(ValidationError):
        await SetPerformerServiceEnabledUseCase(repository).execute(
            SetPerformerServiceEnabledCommand(
                telegram_id=performer.telegram_id,
                service_id=service_id,
                is_enabled=True,
            ),
        )

    await repository.set_current_address(performer_id=performer.id, address_id=uuid4())
    enabled = await SetPerformerServiceEnabledUseCase(repository).execute(
        SetPerformerServiceEnabledCommand(
            telegram_id=performer.telegram_id,
            service_id=service_id,
            is_enabled=True,
        ),
    )

    assert enabled.is_enabled is True


@pytest.mark.asyncio
async def test_only_active_performer_can_accept_orders() -> None:
    repository, city_id, documents = make_repository()
    await CreateInvitationUseCase(repository).execute(
        CreateInvitationCommand(
            telegram_id=123,
            created_by_admin_id=uuid4(),
            expires_at=None,
        ),
    )
    performer = await RegisterPerformerUseCase(repository).execute(
        make_register_command(city_id, documents),
    )

    with pytest.raises(NotFoundError):
        await SetPerformerAcceptingOrdersUseCase(repository).execute(
            SetPerformerAcceptingOrdersCommand(
                telegram_id=performer.telegram_id,
                is_accepting_orders=True,
            ),
        )

    await repository.activate(performer.id)
    updated = await SetPerformerAcceptingOrdersUseCase(repository).execute(
        SetPerformerAcceptingOrdersCommand(
            telegram_id=performer.telegram_id,
            is_accepting_orders=True,
        ),
    )

    assert updated.is_accepting_orders is True

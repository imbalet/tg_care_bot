from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.common.domain import NotFoundError, ValidationError
from backend.modules.addresses.application.use_cases import (
    CreateCustomerAddressUseCase,
    CreateOwnerAddressCommand,
    DeletePerformerAddressUseCase,
    SuggestAddressCommand,
    SuggestAddressesUseCase,
)
from backend.modules.availability.application.use_cases import (
    AddCalendarOverrideCommand,
    AddCalendarOverrideUseCase,
    CancelCalendarOverrideCommand,
    CancelCalendarOverrideUseCase,
    CheckPerformerAvailabilityCommand,
    CheckPerformerAvailabilityUseCase,
    GetPerformerCalendarUseCase,
)
from backend.modules.care_objects.application.validation import (
    validate_care_object_fields,
)
from backend.modules.customers.domain import CustomerStatus
from backend.modules.performers.application.dto import PerformerDTO
from backend.modules.performers.application.use_cases import (
    ApprovePerformerServiceCommand,
    ApprovePerformerServiceUseCase,
    GetRegistrationStateUseCase,
    RegisterPerformerCommand,
    RegisterPerformerUseCase,
    RevokePerformerServiceCommand,
    RevokePerformerServiceUseCase,
    SetPerformerAcceptingOrdersCommand,
    SetPerformerAcceptingOrdersUseCase,
    SetPerformerServiceEnabledCommand,
    SetPerformerServiceEnabledUseCase,
    SetPerformerServiceMaxObjectsCommand,
    SetPerformerServiceMaxObjectsUseCase,
    UpdatePerformerProfileCommand,
    UpdatePerformerProfileUseCase,
)
from tests.support.fakes import FakeClock


def _registration_command() -> RegisterPerformerCommand:
    return RegisterPerformerCommand(
        telegram_id=100,
        full_name="Performer",
        phone="+79990000000",
        city_id=uuid4(),
        contact_method="telegram",
        about_text="About",
        telegram_username="performer",
        accepted_legal_document_ids=(),
    )


@pytest.mark.unit
async def test_registration_state_covers_registered_invited_expired_and_empty() -> None:
    repository = AsyncMock()
    performer = SimpleNamespace(id=uuid4())
    repository.get_performer_by_telegram_id.side_effect = [performer, None, None, None]
    invitation = SimpleNamespace(
        id=uuid4(),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    expired = SimpleNamespace(
        id=uuid4(),
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    repository.get_pending_invitation.side_effect = [invitation, expired, None]
    clock = FakeClock(datetime.now(UTC))
    use_case = GetRegistrationStateUseCase(repository, clock)

    assert (await use_case.execute(1)).state == "registered"
    assert (await use_case.execute(2)).state == "invited"
    assert (await use_case.execute(3)).state == "no_invitation"
    assert (await use_case.execute(4)).state == "no_invitation"
    repository.mark_invitation_expired.assert_awaited_once_with(expired.id)


@pytest.mark.unit
@pytest.mark.parametrize(
    "mutator",
    [
        lambda repository: setattr(
            repository, "get_city_is_active", AsyncMock(return_value=False)
        ),
        lambda repository: setattr(
            repository,
            "list_active_legal_document_ids",
            AsyncMock(return_value=[uuid4()]),
        ),
        lambda repository: setattr(
            repository, "get_pending_invitation", AsyncMock(return_value=None)
        ),
    ],
)
async def test_performer_registration_rejects_missing_prerequisite(
    mutator: Callable[[AsyncMock], None],
) -> None:
    repository = AsyncMock()
    repository.get_performer_by_telegram_id.return_value = None
    repository.get_city_is_active.return_value = True
    repository.list_active_legal_document_ids.return_value = []
    repository.get_pending_invitation.return_value = SimpleNamespace(
        id=uuid4(),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    mutator(repository)

    with pytest.raises(ValidationError):
        await RegisterPerformerUseCase(repository).execute(_registration_command())

    repository.create_performer_from_invitation.assert_not_awaited()


@pytest.mark.unit
async def test_performer_registration_idempotency_and_expiry() -> None:
    repository = AsyncMock()
    existing = cast(PerformerDTO, SimpleNamespace(id=uuid4()))
    repository.get_performer_by_telegram_id.return_value = existing
    assert (
        await RegisterPerformerUseCase(repository).execute(_registration_command())
        is existing
    )
    repository.create_performer_from_invitation.assert_not_awaited()

    repository.get_performer_by_telegram_id.return_value = None
    repository.get_city_is_active.return_value = True
    repository.list_active_legal_document_ids.return_value = []
    invitation = SimpleNamespace(
        id=uuid4(),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    repository.get_pending_invitation.return_value = invitation
    with pytest.raises(ValidationError, match="expired"):
        await RegisterPerformerUseCase(repository).execute(_registration_command())
    repository.mark_invitation_expired.assert_awaited_once_with(invitation.id)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("phone", "contact_method"),
    [(" ", "telegram"), ("+79990000000", "invalid")],
)
async def test_performer_profile_rejects_invalid_contact_data(
    phone: str,
    contact_method: str,
) -> None:
    repository = AsyncMock()

    with pytest.raises(ValidationError):
        await UpdatePerformerProfileUseCase(repository).execute(
            UpdatePerformerProfileCommand(1, phone, contact_method),
        )
    repository.update_profile.assert_not_awaited()


@pytest.mark.unit
async def test_service_approval_enforces_catalog_and_admin_limits() -> None:
    repository = AsyncMock()
    command = ApprovePerformerServiceCommand(
        performer_id=uuid4(),
        service_id=uuid4(),
        admin_max_objects=2,
        constraints={},
        approved_by_admin_id=uuid4(),
    )
    repository.get_service_order_limit.return_value = 1

    with pytest.raises(ValidationError, match="exceeds"):
        await ApprovePerformerServiceUseCase(repository).execute(command)
    repository.approve_service.assert_not_awaited()

    repository.get_service_order_limit.return_value = None
    with pytest.raises(NotFoundError):
        await ApprovePerformerServiceUseCase(repository).execute(command)


@pytest.mark.unit
async def test_service_enable_requires_approved_service_and_current_address() -> None:
    repository = AsyncMock()
    repository.get_performer_by_telegram_id.return_value = SimpleNamespace(
        current_address_id=None,
    )
    service = SimpleNamespace(
        service_id=uuid4(),
        is_approved=True,
        service_location_policy="performer_address",
    )
    repository.list_services_by_telegram_id.return_value = [service]

    with pytest.raises(ValidationError, match="address"):
        await SetPerformerServiceEnabledUseCase(repository).execute(
            SetPerformerServiceEnabledCommand(1, service.service_id, True),
        )
    repository.set_service_enabled_by_telegram_id.assert_not_awaited()

    service.is_approved = False
    service.service_location_policy = "customer_address"
    with pytest.raises(ValidationError, match="approved"):
        await SetPerformerServiceEnabledUseCase(repository).execute(
            SetPerformerServiceEnabledCommand(1, service.service_id, True),
        )


@pytest.mark.unit
async def test_service_max_objects_cannot_exceed_admin_limit() -> None:
    repository = AsyncMock()
    service = SimpleNamespace(service_id=uuid4(), admin_max_objects=1)
    repository.list_services_by_telegram_id.return_value = [service]

    with pytest.raises(ValidationError, match="admin limit"):
        await SetPerformerServiceMaxObjectsUseCase(repository).execute(
            SetPerformerServiceMaxObjectsCommand(1, service.service_id, 2),
        )
    repository.set_service_max_objects_by_telegram_id.assert_not_awaited()


@pytest.mark.unit
async def test_accepting_orders_requires_an_enabled_approved_service() -> None:
    repository = AsyncMock()
    repository.list_services_by_telegram_id.return_value = []

    with pytest.raises(ValidationError, match="approved service"):
        await SetPerformerAcceptingOrdersUseCase(repository).execute(
            SetPerformerAcceptingOrdersCommand(1, True),
        )

    repository.set_accepting_orders_by_telegram_id.assert_not_awaited()


@pytest.mark.unit
async def test_service_revoke_preserves_assignment_and_delegates_to_repository() -> (
    None
):
    repository = AsyncMock()
    service = SimpleNamespace(id=uuid4(), is_approved=False, is_enabled=False)
    repository.revoke_service.return_value = service
    performer_id = uuid4()
    service_id = uuid4()

    result = await RevokePerformerServiceUseCase(repository).execute(
        RevokePerformerServiceCommand(performer_id, service_id),
    )

    assert result is service
    repository.revoke_service.assert_awaited_once_with(
        performer_id=performer_id,
        service_id=service_id,
    )


@pytest.mark.unit
async def test_service_revoke_rejects_unknown_assignment() -> None:
    repository = AsyncMock()
    repository.revoke_service.return_value = None

    with pytest.raises(NotFoundError, match="Performer service"):
        await RevokePerformerServiceUseCase(repository).execute(
            RevokePerformerServiceCommand(uuid4(), uuid4()),
        )


@pytest.mark.unit
async def test_address_suggestion_skips_blank_and_rejects_unknown_city() -> None:
    addresses = AsyncMock()
    geocoder = AsyncMock()
    use_case = SuggestAddressesUseCase(addresses, geocoder)

    assert await use_case.execute(SuggestAddressCommand(uuid4(), " ")) == ()
    geocoder.suggest.assert_not_awaited()

    addresses.get_city_name.return_value = None
    with pytest.raises(ValidationError, match="City"):
        await use_case.execute(SuggestAddressCommand(uuid4(), "street"))


@pytest.mark.unit
async def test_customer_address_creation_requires_active_customer() -> None:
    customers = AsyncMock()
    addresses = AsyncMock()
    geocoder = AsyncMock()
    customers.get_by_telegram_id.return_value = SimpleNamespace(
        id=uuid4(),
        status=CustomerStatus.BLOCKED,
    )

    with pytest.raises(ValidationError, match="addresses"):
        await CreateCustomerAddressUseCase(customers, addresses, geocoder).execute(
            command=CreateOwnerAddressCommand(
                telegram_id=1,
                city_id=uuid4(),
                unrestricted_value="Moscow",
            ),
        )
    geocoder.normalize.assert_not_awaited()


@pytest.mark.unit
async def test_current_performer_address_cannot_be_deleted() -> None:
    performers = AsyncMock()
    addresses = AsyncMock()
    address_id = uuid4()
    performers.get_performer_by_telegram_id.return_value = SimpleNamespace(
        id=uuid4(),
        current_address_id=address_id,
    )

    with pytest.raises(ValidationError, match="Current performer address"):
        await DeletePerformerAddressUseCase(performers, addresses).execute(
            telegram_id=1,
            address_id=address_id,
        )
    addresses.soft_delete.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("object_type", "mobility_assistance_required"),
    [
        ("child", True),
        ("pet", None),
    ],
)
def test_care_object_validation_rejects_incomplete_object_data(
    object_type: str,
    mobility_assistance_required: bool | None,
) -> None:
    with pytest.raises(ValidationError):
        validate_care_object_fields(
            object_type=object_type,
            age_group="adult",
            species=None,
            breed=None,
            pet_size=None,
            mobility_assistance_required=mobility_assistance_required,
        )


@pytest.mark.unit
async def test_calendar_override_and_availability_forward_valid_business_data() -> None:
    repository = AsyncMock()
    override = SimpleNamespace(id=uuid4())
    repository.add_override.return_value = override
    starts_at = datetime.now(UTC) + timedelta(hours=1)
    ends_at = starts_at + timedelta(hours=2)

    override_result = await AddCalendarOverrideUseCase(repository).execute(
        AddCalendarOverrideCommand(1, "unavailable", starts_at, ends_at, "leave"),
    )
    assert override_result.id == override.id

    availability = SimpleNamespace(is_available=True)
    repository.check.return_value = availability
    availability_result = await CheckPerformerAvailabilityUseCase(repository).execute(
        CheckPerformerAvailabilityCommand(uuid4(), uuid4(), starts_at, ends_at),
    )
    assert availability_result.is_available
    repository.check.assert_awaited_once()


@pytest.mark.unit
async def test_calendar_override_can_be_cancelled_by_owner() -> None:
    repository = AsyncMock()
    override = SimpleNamespace(id=uuid4())
    repository.cancel_override.return_value = override

    result = await CancelCalendarOverrideUseCase(repository).execute(
        CancelCalendarOverrideCommand(telegram_id=1, override_id=override.id),
    )

    assert result.id == override.id
    repository.cancel_override.assert_awaited_once_with(
        telegram_id=1,
        override_id=override.id,
    )


@pytest.mark.unit
async def test_calendar_override_cancel_requires_existing_active_override() -> None:
    repository = AsyncMock()
    repository.cancel_override.return_value = None

    with pytest.raises(NotFoundError, match="Active calendar override"):
        await CancelCalendarOverrideUseCase(repository).execute(
            CancelCalendarOverrideCommand(telegram_id=1, override_id=uuid4()),
        )


@pytest.mark.unit
async def test_calendar_use_cases_reject_invalid_ranges_and_unknown_performer() -> None:
    repository = AsyncMock()
    starts_at = datetime.now(UTC) + timedelta(hours=2)
    ends_at = starts_at - timedelta(minutes=1)

    with pytest.raises(ValidationError):
        await AddCalendarOverrideUseCase(repository).execute(
            AddCalendarOverrideCommand(1, "invalid", starts_at, starts_at, None),
        )
    with pytest.raises(ValidationError):
        await CheckPerformerAvailabilityUseCase(repository).execute(
            CheckPerformerAvailabilityCommand(uuid4(), uuid4(), starts_at, ends_at),
        )

    repository.get_calendar_by_telegram_id.return_value = None
    with pytest.raises(NotFoundError):
        await GetPerformerCalendarUseCase(repository).execute(1)

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from backend.common.domain import ConflictError, ValidationError
from backend.modules.addresses.application.use_cases import (
    CreateCustomerAddressUseCase,
    CreateOwnerAddressCommand,
    DeletePerformerAddressUseCase,
)
from backend.modules.care_objects.application.use_cases import (
    CreateCustomerCareObjectCommand,
    CreateCustomerCareObjectUseCase,
)
from backend.modules.customers.domain import CustomerStatus
from backend.modules.performers.application.use_cases import (
    CreateInvitationCommand,
    CreateInvitationUseCase,
    GetRegistrationStateUseCase,
)
from tests.support.fakes import FakeClock


def _active_customer(customer_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=customer_id or uuid4(),
        status=CustomerStatus.ACTIVE,
    )


@pytest.mark.unit
async def test_care_object_creation_rejects_blocked_customer() -> None:
    customers = AsyncMock()
    care_objects = AsyncMock()
    customers.get_by_telegram_id.return_value = SimpleNamespace(
        id=uuid4(),
        status=SimpleNamespace(value="blocked"),
    )

    with pytest.raises(ValidationError, match="cannot manage"):
        await CreateCustomerCareObjectUseCase(customers, care_objects).execute(
            CreateCustomerCareObjectCommand(
                telegram_id=100,
                object_type="pet",
                display_name="Pet",
                age_group="adult",
            ),
        )

    care_objects.add.assert_not_awaited()


@pytest.mark.unit
async def test_customer_address_uses_normalized_geocoder_result() -> None:
    customers = AsyncMock()
    addresses = AsyncMock()
    customers.get_by_telegram_id.return_value = _active_customer()
    geocoder = SimpleNamespace(
        normalize=AsyncMock(
            return_value=SimpleNamespace(
                address_text="Moscow, Test street, 1",
                fias_id="fias",
                latitude=None,
                longitude=None,
                provider="fake",
                quality="high",
            ),
        ),
    )
    addresses.add.return_value = "address"

    await CreateCustomerAddressUseCase(
        customers,
        addresses,
        geocoder,
    ).execute(
        CreateOwnerAddressCommand(
            telegram_id=100,
            city_id=uuid4(),
            unrestricted_value="Moscow, Test street, 1",
        ),
    )

    command = addresses.add.await_args.args[0]
    assert command.owner_type == "customer"
    assert command.address_text == "Moscow, Test street, 1"
    assert command.geocoding_provider == "fake"


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
            telegram_id=100,
            address_id=address_id,
        )

    addresses.soft_delete.assert_not_awaited()


@pytest.mark.unit
async def test_invitation_creation_rejects_registered_performer() -> None:
    repository = AsyncMock()
    repository.get_performer_by_telegram_id.return_value = SimpleNamespace(id=uuid4())

    with pytest.raises(ConflictError):
        await CreateInvitationUseCase(repository).execute(
            CreateInvitationCommand(
                telegram_id=100,
                created_by_admin_id=uuid4(),
                expires_at=None,
            ),
        )

    repository.create_invitation.assert_not_awaited()


@pytest.mark.unit
async def test_expired_invitation_is_marked_and_not_returned() -> None:
    repository = AsyncMock()
    invitation = SimpleNamespace(
        id=uuid4(),
        expires_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    repository.get_performer_by_telegram_id.return_value = None
    repository.get_pending_invitation.return_value = invitation

    state = await GetRegistrationStateUseCase(
        repository,
        FakeClock(datetime(2026, 1, 2, tzinfo=UTC)),
    ).execute(100)

    assert state.state == "no_invitation"
    repository.mark_invitation_expired.assert_awaited_once_with(invitation.id)

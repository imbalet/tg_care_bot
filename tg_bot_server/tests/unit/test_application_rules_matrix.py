from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from backend.common.domain import ConflictError, NotFoundError, ValidationError
from backend.modules.addresses.application.use_cases import (
    CreateOwnerAddressCommand,
    CreatePerformerAddressUseCase,
    DeleteCustomerAddressUseCase,
    SetPerformerCurrentAddressUseCase,
)
from backend.modules.admin.application.use_cases import (
    BootstrapAdminCommand,
    BootstrapAdminUseCase,
    GetCurrentAdminUseCase,
    LogoutAdminUseCase,
)
from backend.modules.admin.domain import Admin
from backend.modules.availability.application.use_cases import (
    AddCalendarOverrideCommand,
    AddCalendarOverrideUseCase,
    CheckPerformerAvailabilityCommand,
    CheckPerformerAvailabilityUseCase,
    FindSuitablePerformersCommand,
    FindSuitablePerformersUseCase,
    SetPerformerScheduleCommand,
    SetPerformerScheduleUseCase,
)
from backend.modules.care_objects.application.use_cases import (
    CreateCustomerCareObjectCommand,
    CreateCustomerCareObjectUseCase,
    DeleteCustomerCareObjectUseCase,
    ListCustomerCareObjectsUseCase,
    UpdateCustomerCareObjectCommand,
    UpdateCustomerCareObjectUseCase,
)
from backend.modules.customers.application.use_cases import (
    GetCustomerProfileUseCase,
    RegisterCustomerCommand,
    RegisterCustomerUseCase,
    UpdateCustomerUsernameCommand,
    UpdateCustomerUsernameUseCase,
)
from backend.modules.customers.domain import ContactMethod, CustomerStatus
from backend.modules.performers.application.use_cases import (
    ApprovePerformerServiceCommand,
    ApprovePerformerServiceUseCase,
    GetRegistrationStateUseCase,
    RegisterPerformerCommand,
    RegisterPerformerUseCase,
    SetPerformerAcceptingOrdersCommand,
    SetPerformerAcceptingOrdersUseCase,
    SetPerformerServiceEnabledCommand,
    SetPerformerServiceEnabledUseCase,
    SetPerformerServiceMaxObjectsCommand,
    SetPerformerServiceMaxObjectsUseCase,
)
from tests.support.fakes import FakeClock


@pytest.mark.unit
async def test_care_object_update_requires_owned_non_deleted_object() -> None:
    customers = AsyncMock()
    objects = AsyncMock()
    customer_id = uuid4()
    object_id = uuid4()
    customers.get_by_telegram_id.return_value = SimpleNamespace(
        id=customer_id,
        status=CustomerStatus.ACTIVE,
    )
    objects.get.return_value = SimpleNamespace(
        customer_id=uuid4(),
        deleted_at=None,
    )

    with pytest.raises(NotFoundError):
        await UpdateCustomerCareObjectUseCase(customers, objects).execute(
            UpdateCustomerCareObjectCommand(
                telegram_id=1,
                care_object_id=object_id,
                display_name="Name",
                age_group="adult",
            ),
        )

    objects.update.assert_not_awaited()


@pytest.mark.unit
async def test_care_object_list_and_delete_delegate_to_owner_repository() -> None:
    customers = AsyncMock()
    objects = AsyncMock()
    customer = SimpleNamespace(id=uuid4(), status=CustomerStatus.ACTIVE)
    customers.get_by_telegram_id.return_value = customer
    objects.get.return_value = SimpleNamespace(customer_id=customer.id)
    objects.has_active_order.return_value = False

    await ListCustomerCareObjectsUseCase(customers, objects).execute(
        telegram_id=1,
        object_type="pet",
    )
    await DeleteCustomerCareObjectUseCase(customers, objects).execute(
        telegram_id=1,
        care_object_id=uuid4(),
    )

    objects.list_for_customer.assert_awaited_once_with(
        customer.id,
        object_type="pet",
    )
    objects.soft_delete.assert_awaited_once()


@pytest.mark.unit
async def test_care_object_delete_rejects_active_order() -> None:
    customers = AsyncMock()
    objects = AsyncMock()
    customer = SimpleNamespace(id=uuid4(), status=CustomerStatus.ACTIVE)
    customers.get_by_telegram_id.return_value = customer
    objects.get.return_value = SimpleNamespace(customer_id=customer.id)
    objects.has_active_order.return_value = True

    with pytest.raises(ConflictError, match="active order"):
        await DeleteCustomerCareObjectUseCase(customers, objects).execute(
            telegram_id=1,
            care_object_id=uuid4(),
        )

    objects.soft_delete.assert_not_awaited()


@pytest.mark.unit
async def test_customer_registration_rejects_missing_legal_document() -> None:
    repository = AsyncMock()
    repository.get_city_is_active.return_value = True
    repository.list_active_legal_document_ids.return_value = [uuid4()]
    command = RegisterCustomerCommand(
        telegram_id=1,
        full_name="Customer",
        phone="+79990000000",
        city_id=uuid4(),
        contact_method="telegram",
        telegram_username=None,
        accepted_legal_document_ids=(),
    )

    with pytest.raises(ValidationError, match="legal"):
        await RegisterCustomerUseCase(repository).execute(command)

    repository.add.assert_not_awaited()


@pytest.mark.unit
async def test_customer_profile_and_username_update_handle_missing_customer() -> None:
    repository = AsyncMock()
    repository.get_by_telegram_id.return_value = None

    with pytest.raises(NotFoundError):
        await GetCustomerProfileUseCase(repository).execute(1)
    with pytest.raises(NotFoundError):
        await UpdateCustomerUsernameUseCase(repository).execute(
            UpdateCustomerUsernameCommand(1, "user"),
        )


@pytest.mark.unit
async def test_performer_address_sets_current_address_on_first_address() -> None:
    performers = AsyncMock()
    addresses = AsyncMock()
    performer_id = uuid4()
    address_id = uuid4()
    performers.get_performer_by_telegram_id.return_value = SimpleNamespace(
        id=performer_id,
        current_address_id=None,
    )
    addresses.add.return_value = SimpleNamespace(id=address_id)
    geocoder = SimpleNamespace(
        normalize=AsyncMock(
            return_value=SimpleNamespace(
                address_text="Moscow, Main street, 1",
                fias_id="fias",
                latitude=None,
                longitude=None,
                provider="fake",
                quality="high",
            ),
        ),
    )

    await CreatePerformerAddressUseCase(performers, addresses, geocoder).execute(
        CreateOwnerAddressCommand(
            telegram_id=1,
            city_id=uuid4(),
            unrestricted_value="Moscow, Main street, 1",
        ),
    )

    performers.set_current_address.assert_awaited_once_with(
        performer_id=performer_id,
        address_id=address_id,
    )


@pytest.mark.unit
async def test_customer_address_delete_rejects_foreign_address() -> None:
    customers = AsyncMock()
    addresses = AsyncMock()
    customer_id = uuid4()
    customers.get_by_telegram_id.return_value = SimpleNamespace(id=customer_id)
    addresses.get.return_value = SimpleNamespace(customer_id=uuid4())

    with pytest.raises(NotFoundError):
        await DeleteCustomerAddressUseCase(customers, addresses).execute(
            telegram_id=1,
            address_id=uuid4(),
        )

    addresses.soft_delete.assert_not_awaited()


@pytest.mark.unit
async def test_availability_validates_schedule_and_override_rules() -> None:
    repository = AsyncMock()
    command = SetPerformerScheduleCommand(
        telegram_id=1,
        schedule_type="custom",
        work_days=(1, 8),
        work_start_time=datetime.strptime("09:00", "%H:%M").time(),
        work_end_time=datetime.strptime("18:00", "%H:%M").time(),
    )

    with pytest.raises(ValidationError, match="between"):
        await SetPerformerScheduleUseCase(repository).execute(command)

    with pytest.raises(ValidationError, match="Override start"):
        await AddCalendarOverrideUseCase(repository).execute(
            AddCalendarOverrideCommand(
                telegram_id=1,
                override_type="available",
                starts_at=datetime(2026, 1, 2, tzinfo=UTC),
                ends_at=datetime(2026, 1, 2, tzinfo=UTC),
                comment=None,
            ),
        )


@pytest.mark.unit
async def test_availability_queries_reject_invalid_intervals_and_limits() -> None:
    checker = AsyncMock()
    finder = AsyncMock()
    start = datetime(2026, 1, 2, tzinfo=UTC)

    with pytest.raises(ValidationError):
        await CheckPerformerAvailabilityUseCase(checker).execute(
            CheckPerformerAvailabilityCommand(uuid4(), uuid4(), start, start),
        )
    with pytest.raises(ValidationError, match="between"):
        await FindSuitablePerformersUseCase(finder).execute(
            FindSuitablePerformersCommand(
                city_id=uuid4(),
                service_id=uuid4(),
                starts_at=start,
                ends_at=start + timedelta(hours=1),
                objects_count=1,
                care_object_ids=(),
                address_id=None,
                limit=101,
            ),
        )


@pytest.mark.unit
async def test_performer_registration_requires_invitation() -> None:
    repository = AsyncMock()
    repository.get_performer_by_telegram_id.return_value = None
    repository.get_city_is_active.return_value = True
    repository.list_active_legal_document_ids.return_value = []
    repository.get_pending_invitation.return_value = None
    command = RegisterPerformerCommand(
        telegram_id=1,
        full_name="Performer",
        phone="+79990000000",
        city_id=uuid4(),
        contact_method="telegram",
        about_text="About",
        telegram_username=None,
        accepted_legal_document_ids=(),
    )

    with pytest.raises(ValidationError, match="Invitation"):
        await RegisterPerformerUseCase(repository).execute(command)


@pytest.mark.unit
async def test_performer_service_approval_and_enable_enforce_limits() -> None:
    repository = AsyncMock()
    service_id = uuid4()
    repository.get_service_order_limit.return_value = 2

    with pytest.raises(ValidationError, match="exceeds"):
        await ApprovePerformerServiceUseCase(repository).execute(
            ApprovePerformerServiceCommand(
                performer_id=uuid4(),
                service_id=service_id,
                admin_max_objects=3,
                constraints={},
                approved_by_admin_id=uuid4(),
            ),
        )

    performer = SimpleNamespace(id=uuid4(), current_address_id=None)
    service = SimpleNamespace(
        service_id=service_id,
        is_approved=True,
        service_location_policy="performer_address",
    )
    repository.get_performer_by_telegram_id.return_value = performer
    repository.list_services_by_telegram_id.return_value = [service]

    with pytest.raises(ValidationError, match="address"):
        await SetPerformerServiceEnabledUseCase(repository).execute(
            SetPerformerServiceEnabledCommand(1, service_id, True),
        )


@pytest.mark.unit
async def test_performer_registration_returns_existing_performer_idempotently() -> None:
    repository = AsyncMock()
    existing = SimpleNamespace(id=uuid4())
    repository.get_performer_by_telegram_id.return_value = existing

    result = await RegisterPerformerUseCase(repository).execute(
        RegisterPerformerCommand(
            telegram_id=1,
            full_name="Performer",
            phone="+79990000000",
            city_id=uuid4(),
            contact_method="invalid",
            about_text="About",
            telegram_username=None,
            accepted_legal_document_ids=(),
        ),
    )

    assert result.id == existing.id
    repository.create_performer_from_invitation.assert_not_awaited()


@pytest.mark.unit
async def test_care_object_create_and_update_forward_owner_data() -> None:
    customers = AsyncMock()
    objects = AsyncMock()
    customer = SimpleNamespace(id=uuid4(), status=CustomerStatus.ACTIVE)
    customers.get_by_telegram_id.return_value = customer
    objects.get.return_value = SimpleNamespace(
        customer_id=customer.id,
        deleted_at=None,
    )

    await CreateCustomerCareObjectUseCase(customers, objects).execute(
        CreateCustomerCareObjectCommand(
            telegram_id=1,
            object_type="pet",
            display_name="Buddy",
            age_group="adult",
        ),
    )
    await UpdateCustomerCareObjectUseCase(customers, objects).execute(
        UpdateCustomerCareObjectCommand(
            telegram_id=1,
            care_object_id=uuid4(),
            display_name="Buddy updated",
            age_group="adult",
        ),
    )

    objects.add.assert_awaited_once()
    objects.update.assert_awaited_once()


@pytest.mark.unit
async def test_customer_registration_creates_and_updates_idempotently() -> None:
    repository = AsyncMock()
    repository.get_by_telegram_id.return_value = None
    repository.get_city_is_active.return_value = True
    repository.list_active_legal_document_ids.return_value = []
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    command = RegisterCustomerCommand(
        telegram_id=1,
        full_name="Customer",
        phone="+79990000000",
        city_id=uuid4(),
        contact_method="telegram",
        telegram_username="customer",
        accepted_legal_document_ids=(),
    )

    created = await RegisterCustomerUseCase(repository, clock).execute(command)
    assert created.telegram_id == 1
    repository.add.assert_awaited_once()
    repository.get_by_telegram_id.return_value = SimpleNamespace(
        id=created.id,
        telegram_id=1,
        full_name="Old",
        phone="+70000000000",
        telegram_username=None,
        contact_method=ContactMethod.TELEGRAM,
        city_id=command.city_id,
        status=CustomerStatus.ACTIVE,
    )

    updated = await RegisterCustomerUseCase(repository, clock).execute(command)
    assert updated.full_name == "Customer"
    repository.update.assert_awaited_once()


@pytest.mark.unit
async def test_address_suggestions_and_current_address_update() -> None:
    addresses = AsyncMock()
    geocoder = AsyncMock()
    city_id = uuid4()
    addresses.get_city_name.return_value = "Moscow"
    geocoder.suggest.return_value = (SimpleNamespace(value="street"),)

    from backend.modules.addresses.application.use_cases import (
        SuggestAddressCommand,
        SuggestAddressesUseCase,
    )

    result = await SuggestAddressesUseCase(addresses, geocoder).execute(
        SuggestAddressCommand(city_id, "street"),
    )
    assert len(result) == 1
    geocoder.suggest.assert_awaited_once_with(query="street", city="Moscow")

    performer_id = uuid4()
    address_id = uuid4()
    performers = AsyncMock()
    performers.get_performer_by_telegram_id.return_value = SimpleNamespace(
        id=performer_id,
        current_address_id=None,
    )
    addresses.get.return_value = SimpleNamespace(
        id=address_id,
        performer_id=performer_id,
        deleted_at=None,
    )
    await SetPerformerCurrentAddressUseCase(performers, addresses).execute(
        telegram_id=1,
        address_id=address_id,
    )
    performers.set_current_address.assert_awaited_once_with(
        performer_id=performer_id,
        address_id=address_id,
    )


@pytest.mark.unit
async def test_performer_registration_state_and_service_limits() -> None:
    repository = AsyncMock()
    performer = SimpleNamespace(id=uuid4())
    repository.get_performer_by_telegram_id.return_value = performer
    state = await GetRegistrationStateUseCase(repository).execute(1)
    assert state.state == "registered"

    service_id = uuid4()
    service = SimpleNamespace(
        service_id=service_id,
        admin_max_objects=2,
        is_approved=True,
        is_enabled=True,
        service_location_policy="customer_address",
    )
    repository.get_performer_by_telegram_id.return_value = performer
    repository.list_services_by_telegram_id.return_value = [service]
    repository.set_service_max_objects_by_telegram_id.return_value = service
    result = await SetPerformerServiceMaxObjectsUseCase(repository).execute(
        SetPerformerServiceMaxObjectsCommand(1, service_id, 1),
    )
    assert result.service_id == service.service_id
    repository.set_service_max_objects_by_telegram_id.assert_awaited_once()

    repository.set_accepting_orders_by_telegram_id.return_value = performer
    await SetPerformerAcceptingOrdersUseCase(repository).execute(
        SetPerformerAcceptingOrdersCommand(1, True),
    )


@pytest.mark.unit
async def test_admin_bootstrap_current_session_and_logout() -> None:
    repository = AsyncMock()
    repository.get_by_email.return_value = None
    hasher = Mock()
    hasher.hash.return_value = "hash"
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    admin = await BootstrapAdminUseCase(repository, hasher, clock).execute(
        BootstrapAdminCommand("ADMIN@EXAMPLE.COM", "Admin", "password"),
    )
    assert admin.email == "admin@example.com"
    repository.add.assert_awaited_once()

    sessions = AsyncMock()
    stored_admin = repository.add.await_args.args[0]
    assert isinstance(stored_admin, Admin)
    repository.get_by_id.return_value = stored_admin
    csrf_token = str(uuid4())
    sessions.get.return_value = SimpleNamespace(
        admin_id=admin.id,
        csrf_token=csrf_token,
    )
    current, csrf = await GetCurrentAdminUseCase(repository, sessions).execute(
        "session",
    )
    assert current.id == admin.id
    assert csrf == csrf_token
    await LogoutAdminUseCase(sessions).execute("session")
    sessions.delete.assert_awaited_once_with("session")

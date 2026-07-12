from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from backend.common.domain import NotFoundError, ValidationError
from backend.modules.care_objects.application import (
    CareObjectDTO,
    CreateCareObjectCommand,
    CreateCustomerCareObjectCommand,
    CreateCustomerCareObjectUseCase,
    DeleteCustomerCareObjectUseCase,
    ListCustomerCareObjectsUseCase,
    UpdateCareObjectCommand,
    UpdateCustomerCareObjectCommand,
    UpdateCustomerCareObjectUseCase,
)
from backend.modules.customers.domain import ContactMethod, Customer, CustomerStatus


class FakeCustomerRepository:
    def __init__(self, customer: Customer | None) -> None:
        self.customer = customer

    async def get_by_telegram_id(self, telegram_id: int) -> Customer | None:
        if self.customer is not None and self.customer.telegram_id == telegram_id:
            return self.customer
        return None

    async def get_city_is_active(self, city_id: UUID) -> bool:
        del city_id
        return False

    async def list_active_legal_document_ids(self) -> tuple[UUID, ...]:
        return ()

    async def add(self, customer: Customer) -> None:
        self.customer = customer

    async def add_legal_acceptances(
        self,
        *,
        customer_id: UUID,
        document_ids: tuple[UUID, ...],
    ) -> None:
        del customer_id, document_ids

    async def update(self, customer: Customer) -> None:
        self.customer = customer


class FakeCareObjectRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, CareObjectDTO] = {}

    async def get(self, care_object_id: UUID) -> CareObjectDTO | None:
        return self.items.get(care_object_id)

    async def add(self, command: CreateCareObjectCommand) -> CareObjectDTO:
        care_object = _make_care_object(
            customer_id=command.customer_id,
            object_type=command.object_type,
            display_name=command.display_name,
            age_group=command.age_group,
            species=command.species,
            breed=command.breed,
            pet_size=command.pet_size,
            mobility_assistance_required=command.mobility_assistance_required,
            routine_notes=command.routine_notes,
            behavior_notes=command.behavior_notes,
        )
        self.items[care_object.id] = care_object
        return care_object

    async def update(self, command: UpdateCareObjectCommand) -> CareObjectDTO:
        existing = self.items[command.care_object_id]
        updated = CareObjectDTO(
            id=existing.id,
            customer_id=existing.customer_id,
            object_type=existing.object_type,
            display_name=command.display_name,
            age_group=command.age_group,
            species=command.species,
            breed=command.breed,
            pet_size=command.pet_size,
            mobility_assistance_required=command.mobility_assistance_required,
            routine_notes=command.routine_notes,
            behavior_notes=command.behavior_notes,
            deleted_at=existing.deleted_at,
            created_at=existing.created_at,
            updated_at=datetime.now(UTC),
        )
        self.items[updated.id] = updated
        return updated

    async def soft_delete(self, care_object_id: UUID) -> None:
        existing = self.items[care_object_id]
        deleted = CareObjectDTO(
            id=existing.id,
            customer_id=existing.customer_id,
            object_type=existing.object_type,
            display_name=existing.display_name,
            age_group=existing.age_group,
            species=existing.species,
            breed=existing.breed,
            pet_size=existing.pet_size,
            mobility_assistance_required=existing.mobility_assistance_required,
            routine_notes=existing.routine_notes,
            behavior_notes=existing.behavior_notes,
            deleted_at=datetime.now(UTC),
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )
        self.items[care_object_id] = deleted

    async def list_for_customer(
        self,
        customer_id: UUID,
        *,
        active_only: bool = True,
        object_type: str | None = None,
    ) -> tuple[CareObjectDTO, ...]:
        items = [
            item
            for item in self.items.values()
            if item.customer_id == customer_id
            and (not active_only or item.deleted_at is None)
            and (object_type is None or item.object_type == object_type)
        ]
        return tuple(items)


def _make_customer(status: CustomerStatus = CustomerStatus.ACTIVE) -> Customer:
    now = datetime.now(UTC)
    return Customer(
        id=uuid4(),
        telegram_id=123,
        full_name="Customer",
        phone="+79990000000",
        telegram_username=None,
        contact_method=ContactMethod.BOTH,
        city_id=uuid4(),
        status=status,
        blocked_reason=None,
        deleted_at=None,
        anonymized_at=None,
        created_at=now,
        updated_at=now,
    )


def _make_care_object(
    *,
    customer_id: UUID,
    object_type: str = "child",
    display_name: str = "Name",
    age_group: str = "school_age",
    species: str | None = None,
    breed: str | None = None,
    pet_size: str | None = None,
    mobility_assistance_required: bool | None = None,
    routine_notes: str | None = None,
    behavior_notes: str | None = None,
) -> CareObjectDTO:
    now = datetime.now(UTC)
    return CareObjectDTO(
        id=uuid4(),
        customer_id=customer_id,
        object_type=object_type,
        display_name=display_name,
        age_group=age_group,
        species=species,
        breed=breed,
        pet_size=pet_size,
        mobility_assistance_required=mobility_assistance_required,
        routine_notes=routine_notes,
        behavior_notes=behavior_notes,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_create_customer_care_object_creates_pet() -> None:
    customer = _make_customer()
    repository = FakeCareObjectRepository()

    care_object = await CreateCustomerCareObjectUseCase(
        FakeCustomerRepository(customer),
        repository,
    ).execute(
        CreateCustomerCareObjectCommand(
            telegram_id=customer.telegram_id,
            object_type="pet",
            display_name="Barsik",
            age_group="adult",
            species="cat",
            breed=None,
            pet_size="small",
        ),
    )

    assert care_object.customer_id == customer.id
    assert care_object.object_type == "pet"
    assert care_object.species == "cat"


@pytest.mark.asyncio
async def test_create_customer_care_object_rejects_blocked_customer() -> None:
    customer = _make_customer(CustomerStatus.BLOCKED)

    with pytest.raises(ValidationError):
        await CreateCustomerCareObjectUseCase(
            FakeCustomerRepository(customer),
            FakeCareObjectRepository(),
        ).execute(
            CreateCustomerCareObjectCommand(
                telegram_id=customer.telegram_id,
                object_type="child",
                display_name="Child",
                age_group="school_age",
            ),
        )


@pytest.mark.asyncio
async def test_update_customer_care_object_rejects_other_customer_object() -> None:
    customer = _make_customer()
    repository = FakeCareObjectRepository()
    care_object = _make_care_object(customer_id=uuid4())
    repository.items[care_object.id] = care_object

    with pytest.raises(NotFoundError):
        await UpdateCustomerCareObjectUseCase(
            FakeCustomerRepository(customer),
            repository,
        ).execute(
            UpdateCustomerCareObjectCommand(
                telegram_id=customer.telegram_id,
                care_object_id=care_object.id,
                display_name="Updated",
                age_group="school_age",
            ),
        )


@pytest.mark.asyncio
async def test_delete_customer_care_object_hides_from_active_list() -> None:
    customer = _make_customer()
    repository = FakeCareObjectRepository()
    care_object = _make_care_object(customer_id=customer.id)
    repository.items[care_object.id] = care_object

    await DeleteCustomerCareObjectUseCase(
        FakeCustomerRepository(customer),
        repository,
    ).execute(telegram_id=customer.telegram_id, care_object_id=care_object.id)
    active = await ListCustomerCareObjectsUseCase(
        FakeCustomerRepository(customer),
        repository,
    ).execute(telegram_id=customer.telegram_id, object_type=None)

    assert active == ()

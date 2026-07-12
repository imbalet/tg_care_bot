from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from backend.common.domain import NotFoundError, ValidationError
from backend.modules.customers.application import (
    RegisterCustomerCommand,
    RegisterCustomerUseCase,
    UpdateCustomerUsernameCommand,
    UpdateCustomerUsernameUseCase,
)
from backend.modules.customers.domain import ContactMethod, Customer, CustomerStatus


class FakeCustomerRepository:
    def __init__(self) -> None:
        self.customers: dict[int, Customer] = {}
        self.active_city_ids: set[UUID] = set()
        self.active_document_ids: tuple[UUID, ...] = ()
        self.acceptances: dict[UUID, set[UUID]] = {}

    async def get_by_telegram_id(self, telegram_id: int) -> Customer | None:
        return self.customers.get(telegram_id)

    async def get_city_is_active(self, city_id: UUID) -> bool:
        return city_id in self.active_city_ids

    async def list_active_legal_document_ids(self) -> tuple[UUID, ...]:
        return self.active_document_ids

    async def add(self, customer: Customer) -> None:
        self.customers[customer.telegram_id] = customer

    async def add_legal_acceptances(
        self,
        *,
        customer_id: UUID,
        document_ids: tuple[UUID, ...],
    ) -> None:
        self.acceptances.setdefault(customer_id, set()).update(document_ids)

    async def update(self, customer: Customer) -> None:
        self.customers[customer.telegram_id] = customer


def make_command(
    city_id: UUID, document_ids: tuple[UUID, ...]
) -> RegisterCustomerCommand:
    return RegisterCustomerCommand(
        telegram_id=123,
        full_name="Customer User",
        phone="+79990000000",
        city_id=city_id,
        contact_method="both",
        telegram_username="customer",
        accepted_legal_document_ids=document_ids,
    )


def make_repository() -> tuple[FakeCustomerRepository, UUID, tuple[UUID, ...]]:
    city_id = uuid4()
    document_ids = (uuid4(), uuid4())
    repository = FakeCustomerRepository()
    repository.active_city_ids.add(city_id)
    repository.active_document_ids = document_ids
    return repository, city_id, document_ids


@pytest.mark.asyncio
async def test_register_customer_creates_active_customer() -> None:
    repository, city_id, document_ids = make_repository()

    customer = await RegisterCustomerUseCase(repository).execute(
        make_command(city_id, document_ids),
    )

    assert customer.telegram_id == 123
    assert customer.status == "active"
    assert repository.acceptances[customer.id] == set(document_ids)


@pytest.mark.asyncio
async def test_register_customer_is_idempotent_for_same_telegram_id() -> None:
    repository, city_id, document_ids = make_repository()
    use_case = RegisterCustomerUseCase(repository)
    first = await use_case.execute(make_command(city_id, document_ids))

    second = await use_case.execute(
        replace(
            make_command(city_id, document_ids),
            full_name="Updated Customer",
            telegram_username=None,
        ),
    )

    assert second.id == first.id
    assert second.full_name == "Updated Customer"
    assert second.telegram_username is None


@pytest.mark.asyncio
async def test_register_customer_rejects_missing_legal_acceptance() -> None:
    repository, city_id, document_ids = make_repository()

    with pytest.raises(ValidationError):
        await RegisterCustomerUseCase(repository).execute(
            make_command(city_id, document_ids[:1]),
        )


@pytest.mark.asyncio
async def test_register_customer_rejects_inactive_city() -> None:
    repository, _city_id, document_ids = make_repository()

    with pytest.raises(ValidationError):
        await RegisterCustomerUseCase(repository).execute(
            make_command(uuid4(), document_ids),
        )


@pytest.mark.asyncio
async def test_update_customer_username_to_value_and_null() -> None:
    repository, city_id, _document_ids = make_repository()
    now = datetime.now(UTC)
    customer = Customer(
        id=uuid4(),
        telegram_id=123,
        full_name="Customer User",
        phone="+79990000000",
        telegram_username=None,
        contact_method=ContactMethod.BOTH,
        city_id=city_id,
        status=CustomerStatus.ACTIVE,
        blocked_reason=None,
        deleted_at=None,
        anonymized_at=None,
        created_at=now,
        updated_at=now,
    )
    repository.customers[customer.telegram_id] = customer
    use_case = UpdateCustomerUsernameUseCase(repository)

    with_value = await use_case.execute(
        UpdateCustomerUsernameCommand(telegram_id=123, telegram_username="new_name"),
    )
    without_value = await use_case.execute(
        UpdateCustomerUsernameCommand(telegram_id=123, telegram_username=None),
    )

    assert with_value.telegram_username == "new_name"
    assert without_value.telegram_username is None


@pytest.mark.asyncio
async def test_update_customer_username_rejects_unknown_customer() -> None:
    repository, _city_id, _document_ids = make_repository()

    with pytest.raises(NotFoundError):
        await UpdateCustomerUsernameUseCase(repository).execute(
            UpdateCustomerUsernameCommand(telegram_id=123, telegram_username=None),
        )

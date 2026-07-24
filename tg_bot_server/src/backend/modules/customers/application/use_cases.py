from dataclasses import dataclass
from uuid import UUID

from backend.common.application import Clock, SystemClock, new_uuid
from backend.common.domain import NotFoundError, ValidationError
from backend.modules.customers.application.dto import CustomerDTO
from backend.modules.customers.application.interfaces import CustomerRepository
from backend.modules.customers.domain import ContactMethod, Customer, CustomerStatus


def _to_dto(customer: Customer) -> CustomerDTO:
    return CustomerDTO(
        id=customer.id,
        telegram_id=customer.telegram_id,
        full_name=customer.full_name,
        phone=customer.phone,
        telegram_username=customer.telegram_username,
        contact_method=customer.contact_method.value,
        city_id=customer.city_id,
        status=customer.status.value,
    )


@dataclass(frozen=True)
class RegisterCustomerCommand:
    telegram_id: int
    full_name: str
    phone: str
    city_id: UUID
    contact_method: str
    telegram_username: str | None
    accepted_legal_document_ids: tuple[UUID, ...]


class RegisterCustomerUseCase:
    def __init__(
        self,
        repository: CustomerRepository,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or SystemClock()

    async def execute(self, command: RegisterCustomerCommand) -> CustomerDTO:
        await self._validate(command)
        existing = await self._repository.get_by_telegram_id(command.telegram_id)
        if existing is not None:
            existing.full_name = command.full_name
            existing.phone = command.phone
            existing.city_id = command.city_id
            existing.contact_method = ContactMethod(command.contact_method)
            existing.telegram_username = command.telegram_username
            existing.updated_at = self._clock.now()
            await self._repository.update(existing)
            await self._repository.add_legal_acceptances(
                customer_id=existing.id,
                document_ids=command.accepted_legal_document_ids,
            )
            return _to_dto(existing)

        now = self._clock.now()
        customer = Customer(
            id=new_uuid(),
            telegram_id=command.telegram_id,
            full_name=command.full_name,
            phone=command.phone,
            telegram_username=command.telegram_username,
            contact_method=ContactMethod(command.contact_method),
            city_id=command.city_id,
            status=CustomerStatus.ACTIVE,
            blocked_reason=None,
            deleted_at=None,
            anonymized_at=None,
            created_at=now,
            updated_at=now,
        )
        await self._repository.add(customer)
        await self._repository.add_legal_acceptances(
            customer_id=customer.id,
            document_ids=command.accepted_legal_document_ids,
        )
        return _to_dto(customer)

    async def _validate(self, command: RegisterCustomerCommand) -> None:
        if not command.full_name.strip():
            raise ValidationError("Full name is required")
        if not command.phone.strip():
            raise ValidationError("Phone is required")
        try:
            ContactMethod(command.contact_method)
        except ValueError as exc:
            raise ValidationError("Contact method is invalid") from exc
        if not await self._repository.get_city_is_active(command.city_id):
            raise ValidationError("City is inactive or unknown")
        required_documents = set(
            await self._repository.list_active_legal_document_ids()
        )
        accepted_documents = set(command.accepted_legal_document_ids)
        if not required_documents.issubset(accepted_documents):
            raise ValidationError("Required legal documents are not accepted")


class GetCustomerProfileUseCase:
    def __init__(self, repository: CustomerRepository) -> None:
        self._repository = repository

    async def execute(self, telegram_id: int) -> CustomerDTO:
        customer = await self._repository.get_by_telegram_id(telegram_id)
        if customer is None:
            raise NotFoundError("Customer is not registered")
        return _to_dto(customer)


@dataclass(frozen=True)
class UpdateCustomerUsernameCommand:
    telegram_id: int
    telegram_username: str | None


class UpdateCustomerUsernameUseCase:
    def __init__(
        self,
        repository: CustomerRepository,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or SystemClock()

    async def execute(self, command: UpdateCustomerUsernameCommand) -> CustomerDTO:
        customer = await self._repository.get_by_telegram_id(command.telegram_id)
        if customer is None:
            raise NotFoundError("Customer is not registered")
        if customer.telegram_username != command.telegram_username:
            customer.telegram_username = command.telegram_username
            customer.updated_at = self._clock.now()
            await self._repository.update(customer)
        return _to_dto(customer)


@dataclass(frozen=True)
class UpdateCustomerProfileCommand:
    telegram_id: int
    phone: str
    contact_method: str


class UpdateCustomerProfileUseCase:
    def __init__(
        self,
        repository: CustomerRepository,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or SystemClock()

    async def execute(self, command: UpdateCustomerProfileCommand) -> CustomerDTO:
        if not command.phone.strip():
            raise ValidationError("Phone is required")
        try:
            contact_method = ContactMethod(command.contact_method)
        except ValueError as exc:
            raise ValidationError("Contact method is invalid") from exc
        customer = await self._repository.get_by_telegram_id(command.telegram_id)
        if customer is None:
            raise NotFoundError("Customer is not registered")
        customer.phone = command.phone
        customer.contact_method = contact_method
        customer.updated_at = self._clock.now()
        await self._repository.update(customer)
        return _to_dto(customer)

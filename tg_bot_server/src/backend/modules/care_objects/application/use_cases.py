from dataclasses import dataclass
from uuid import UUID

from backend.common.domain import ConflictError, NotFoundError, ValidationError
from backend.modules.care_objects.application.dto import (
    CareObjectDTO,
    CreateCareObjectCommand,
    UpdateCareObjectCommand,
)
from backend.modules.care_objects.application.interfaces import CareObjectRepository
from backend.modules.customers.application.interfaces import CustomerRepository
from backend.modules.customers.domain import CustomerStatus


def _ensure_customer_can_manage(customer_status: str) -> None:
    if customer_status != CustomerStatus.ACTIVE.value:
        raise ValidationError("Customer cannot manage care objects")


@dataclass(frozen=True)
class CreateCustomerCareObjectCommand:
    telegram_id: int
    object_type: str
    display_name: str
    age_group: str
    species: str | None = None
    breed: str | None = None
    pet_size: str | None = None
    mobility_assistance_required: bool | None = None
    routine_notes: str | None = None
    behavior_notes: str | None = None


@dataclass(frozen=True)
class UpdateCustomerCareObjectCommand:
    telegram_id: int
    care_object_id: UUID
    display_name: str
    age_group: str
    species: str | None = None
    breed: str | None = None
    pet_size: str | None = None
    mobility_assistance_required: bool | None = None
    routine_notes: str | None = None
    behavior_notes: str | None = None


class ListCustomerCareObjectsUseCase:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        care_object_repository: CareObjectRepository,
    ) -> None:
        self._customer_repository = customer_repository
        self._care_object_repository = care_object_repository

    async def execute(
        self,
        *,
        telegram_id: int,
        object_type: str | None,
    ) -> tuple[CareObjectDTO, ...]:
        customer = await self._customer_repository.get_by_telegram_id(telegram_id)
        if customer is None:
            raise NotFoundError("Customer is not registered")
        _ensure_customer_can_manage(customer.status.value)
        return await self._care_object_repository.list_for_customer(
            customer.id,
            object_type=object_type,
        )


class CreateCustomerCareObjectUseCase:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        care_object_repository: CareObjectRepository,
    ) -> None:
        self._customer_repository = customer_repository
        self._care_object_repository = care_object_repository

    async def execute(self, command: CreateCustomerCareObjectCommand) -> CareObjectDTO:
        customer = await self._customer_repository.get_by_telegram_id(
            command.telegram_id,
        )
        if customer is None:
            raise NotFoundError("Customer is not registered")
        _ensure_customer_can_manage(customer.status.value)
        return await self._care_object_repository.add(
            CreateCareObjectCommand(
                customer_id=customer.id,
                object_type=command.object_type,
                display_name=command.display_name,
                age_group=command.age_group,
                species=command.species,
                breed=command.breed,
                pet_size=command.pet_size,
                mobility_assistance_required=command.mobility_assistance_required,
                routine_notes=command.routine_notes,
                behavior_notes=command.behavior_notes,
            ),
        )


class UpdateCustomerCareObjectUseCase:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        care_object_repository: CareObjectRepository,
    ) -> None:
        self._customer_repository = customer_repository
        self._care_object_repository = care_object_repository

    async def execute(self, command: UpdateCustomerCareObjectCommand) -> CareObjectDTO:
        customer = await self._customer_repository.get_by_telegram_id(
            command.telegram_id,
        )
        if customer is None:
            raise NotFoundError("Customer is not registered")
        _ensure_customer_can_manage(customer.status.value)
        care_object = await self._care_object_repository.get(command.care_object_id)
        if care_object is None or care_object.customer_id != customer.id:
            raise NotFoundError("Care object not found")
        if care_object.deleted_at is not None:
            raise NotFoundError("Care object not found")
        return await self._care_object_repository.update(
            UpdateCareObjectCommand(
                care_object_id=command.care_object_id,
                display_name=command.display_name,
                age_group=command.age_group,
                species=command.species,
                breed=command.breed,
                pet_size=command.pet_size,
                mobility_assistance_required=command.mobility_assistance_required,
                routine_notes=command.routine_notes,
                behavior_notes=command.behavior_notes,
            ),
        )


class DeleteCustomerCareObjectUseCase:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        care_object_repository: CareObjectRepository,
    ) -> None:
        self._customer_repository = customer_repository
        self._care_object_repository = care_object_repository

    async def execute(self, *, telegram_id: int, care_object_id: UUID) -> None:
        customer = await self._customer_repository.get_by_telegram_id(telegram_id)
        if customer is None:
            raise NotFoundError("Customer is not registered")
        _ensure_customer_can_manage(customer.status.value)
        care_object = await self._care_object_repository.get(care_object_id)
        if care_object is None or care_object.customer_id != customer.id:
            raise NotFoundError("Care object not found")
        if await self._care_object_repository.has_active_order(care_object_id):
            raise ConflictError(
                "Care object cannot be deleted while an active order uses it",
            )
        await self._care_object_repository.soft_delete(care_object_id)

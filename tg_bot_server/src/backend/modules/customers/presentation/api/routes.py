from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key
from backend.modules.care_objects.application import (
    CareObjectDTO,
    CreateCustomerCareObjectCommand,
    CreateCustomerCareObjectUseCase,
    DeleteCustomerCareObjectUseCase,
    ListCustomerCareObjectsUseCase,
    UpdateCustomerCareObjectCommand,
    UpdateCustomerCareObjectUseCase,
)
from backend.modules.care_objects.infrastructure import SqlAlchemyCareObjectRepository
from backend.modules.customers.application import (
    GetCustomerProfileUseCase,
    RegisterCustomerCommand,
    RegisterCustomerUseCase,
    UpdateCustomerUsernameCommand,
    UpdateCustomerUsernameUseCase,
)
from backend.modules.customers.application.dto import CustomerDTO
from backend.modules.customers.infrastructure import SqlAlchemyCustomerRepository

router = APIRouter(
    prefix="/api/customers",
    tags=["customers"],
    dependencies=[Depends(require_service_key)],
)


class RegisterCustomerRequest(BaseModel):
    telegram_id: int
    full_name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    city_id: UUID
    contact_method: str
    telegram_username: str | None = None
    accepted_legal_document_ids: list[UUID]


class UpdateTelegramUsernameRequest(BaseModel):
    telegram_username: str | None = None


class CustomerResponse(BaseModel):
    id: str
    telegram_id: int
    full_name: str
    phone: str
    telegram_username: str | None
    contact_method: str
    city_id: str
    status: str


class CareObjectRequest(BaseModel):
    display_name: str = Field(min_length=1)
    age_group: str
    species: str | None = None
    breed: str | None = None
    pet_size: str | None = None
    mobility_assistance_required: bool | None = None
    routine_notes: str | None = None
    behavior_notes: str | None = None


class CreateCareObjectRequest(CareObjectRequest):
    object_type: str


class CareObjectResponse(BaseModel):
    id: str
    customer_id: str
    object_type: str
    display_name: str
    age_group: str
    species: str | None
    breed: str | None
    pet_size: str | None
    mobility_assistance_required: bool | None
    routine_notes: str | None
    behavior_notes: str | None
    deleted_at: str | None
    created_at: str
    updated_at: str


def _to_response(customer: CustomerDTO) -> CustomerResponse:
    return CustomerResponse(
        id=str(customer.id),
        telegram_id=customer.telegram_id,
        full_name=customer.full_name,
        phone=customer.phone,
        telegram_username=customer.telegram_username,
        contact_method=customer.contact_method,
        city_id=str(customer.city_id),
        status=customer.status,
    )


def _care_object_to_response(care_object: CareObjectDTO) -> CareObjectResponse:
    return CareObjectResponse(
        id=str(care_object.id),
        customer_id=str(care_object.customer_id),
        object_type=care_object.object_type,
        display_name=care_object.display_name,
        age_group=care_object.age_group,
        species=care_object.species,
        breed=care_object.breed,
        pet_size=care_object.pet_size,
        mobility_assistance_required=care_object.mobility_assistance_required,
        routine_notes=care_object.routine_notes,
        behavior_notes=care_object.behavior_notes,
        deleted_at=care_object.deleted_at.isoformat()
        if care_object.deleted_at is not None
        else None,
        created_at=care_object.created_at.isoformat(),
        updated_at=care_object.updated_at.isoformat(),
    )


@router.get("/by-telegram/{telegram_id}/profile")
async def get_profile(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> CustomerResponse:
    async with container.session_factory() as session:
        customer = await GetCustomerProfileUseCase(
            SqlAlchemyCustomerRepository(session),
        ).execute(telegram_id)
    return _to_response(customer)


@router.post("/register", status_code=201)
async def register(
    request: RegisterCustomerRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CustomerResponse:
    async with container.session_factory() as session:
        customer = await RegisterCustomerUseCase(
            SqlAlchemyCustomerRepository(session),
        ).execute(
            RegisterCustomerCommand(
                telegram_id=request.telegram_id,
                full_name=request.full_name,
                phone=request.phone,
                city_id=request.city_id,
                contact_method=request.contact_method,
                telegram_username=request.telegram_username,
                accepted_legal_document_ids=tuple(request.accepted_legal_document_ids),
            ),
        )
        await session.commit()
    return _to_response(customer)


@router.patch("/by-telegram/{telegram_id}/telegram-username")
async def update_telegram_username(
    telegram_id: int,
    request: UpdateTelegramUsernameRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CustomerResponse:
    async with container.session_factory() as session:
        customer = await UpdateCustomerUsernameUseCase(
            SqlAlchemyCustomerRepository(session),
        ).execute(
            UpdateCustomerUsernameCommand(
                telegram_id=telegram_id,
                telegram_username=request.telegram_username,
            ),
        )
        await session.commit()
    return _to_response(customer)


@router.get("/by-telegram/{telegram_id}/care-objects")
async def list_care_objects(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
    object_type: Annotated[str | None, Query()] = None,
) -> list[CareObjectResponse]:
    async with container.session_factory() as session:
        customer_repository = SqlAlchemyCustomerRepository(session)
        care_object_repository = SqlAlchemyCareObjectRepository(session)
        care_objects = await ListCustomerCareObjectsUseCase(
            customer_repository,
            care_object_repository,
        ).execute(telegram_id=telegram_id, object_type=object_type)
    return [_care_object_to_response(care_object) for care_object in care_objects]


@router.post("/by-telegram/{telegram_id}/care-objects", status_code=201)
async def create_care_object(
    telegram_id: int,
    request: CreateCareObjectRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CareObjectResponse:
    async with container.session_factory() as session:
        care_object = await CreateCustomerCareObjectUseCase(
            SqlAlchemyCustomerRepository(session),
            SqlAlchemyCareObjectRepository(session),
        ).execute(
            CreateCustomerCareObjectCommand(
                telegram_id=telegram_id,
                object_type=request.object_type,
                display_name=request.display_name,
                age_group=request.age_group,
                species=request.species,
                breed=request.breed,
                pet_size=request.pet_size,
                mobility_assistance_required=request.mobility_assistance_required,
                routine_notes=request.routine_notes,
                behavior_notes=request.behavior_notes,
            ),
        )
        await session.commit()
    return _care_object_to_response(care_object)


@router.patch("/by-telegram/{telegram_id}/care-objects/{care_object_id}")
async def update_care_object(
    telegram_id: int,
    care_object_id: UUID,
    request: CareObjectRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CareObjectResponse:
    async with container.session_factory() as session:
        care_object = await UpdateCustomerCareObjectUseCase(
            SqlAlchemyCustomerRepository(session),
            SqlAlchemyCareObjectRepository(session),
        ).execute(
            UpdateCustomerCareObjectCommand(
                telegram_id=telegram_id,
                care_object_id=care_object_id,
                display_name=request.display_name,
                age_group=request.age_group,
                species=request.species,
                breed=request.breed,
                pet_size=request.pet_size,
                mobility_assistance_required=request.mobility_assistance_required,
                routine_notes=request.routine_notes,
                behavior_notes=request.behavior_notes,
            ),
        )
        await session.commit()
    return _care_object_to_response(care_object)


@router.delete("/by-telegram/{telegram_id}/care-objects/{care_object_id}")
async def delete_care_object(
    telegram_id: int,
    care_object_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, str]:
    async with container.session_factory() as session:
        await DeleteCustomerCareObjectUseCase(
            SqlAlchemyCustomerRepository(session),
            SqlAlchemyCareObjectRepository(session),
        ).execute(telegram_id=telegram_id, care_object_id=care_object_id)
        await session.commit()
    return {"status": "deleted"}


__all__ = ["router"]

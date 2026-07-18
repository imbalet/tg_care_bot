from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key
from backend.modules.addresses.application import (
    CreateCustomerAddressUseCase,
    CreateOwnerAddressCommand,
    DeleteCustomerAddressUseCase,
)
from backend.modules.addresses.infrastructure import SqlAlchemyAddressRepository
from backend.modules.care_objects.application import (
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
    RegisterCustomerUseCase,
    UpdateCustomerUsernameUseCase,
)
from backend.modules.customers.infrastructure import SqlAlchemyCustomerRepository
from backend.modules.geo.infrastructure import DaDataGeocoder

from .mappers import (
    address_response,
    care_object_response,
    customer_response,
    register_customer_command,
    update_customer_username_command,
)
from .schemas import (
    AddressResponse,
    CareObjectRequest,
    CareObjectResponse,
    CreateAddressRequest,
    CreateCareObjectRequest,
    CustomerResponse,
    RegisterCustomerRequest,
    UpdateTelegramUsernameRequest,
)

router = APIRouter(
    prefix="/api/customers",
    tags=["customers"],
    dependencies=[Depends(require_service_key)],
)


def _geocoder(container: Container) -> DaDataGeocoder:
    settings = container.settings
    return DaDataGeocoder(
        api_key=settings.dadata_api_key,
        secret_key=settings.dadata_secret_key,
        base_url=settings.dadata_base_url,
        timeout_seconds=settings.dadata_timeout_seconds,
        retry_count=settings.dadata_retry_count,
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
    return customer_response(customer)


@router.post("/register", status_code=201)
async def register(
    request: RegisterCustomerRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CustomerResponse:
    async with container.session_factory() as session:
        customer = await RegisterCustomerUseCase(
            SqlAlchemyCustomerRepository(session),
        ).execute(register_customer_command(request))
        await session.commit()
    return customer_response(customer)


@router.patch("/by-telegram/{telegram_id}/telegram-username")
async def update_telegram_username(
    telegram_id: int,
    request: UpdateTelegramUsernameRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CustomerResponse:
    async with container.session_factory() as session:
        customer = await UpdateCustomerUsernameUseCase(
            SqlAlchemyCustomerRepository(session),
        ).execute(update_customer_username_command(telegram_id, request))
        await session.commit()
    return customer_response(customer)


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
    return [care_object_response(care_object) for care_object in care_objects]


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
    return care_object_response(care_object)


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
    return care_object_response(care_object)


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


@router.get("/by-telegram/{telegram_id}/addresses")
async def list_addresses(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> list[AddressResponse]:
    async with container.session_factory() as session:
        customer = await GetCustomerProfileUseCase(
            SqlAlchemyCustomerRepository(session),
        ).execute(telegram_id)
        addresses = await SqlAlchemyAddressRepository(session).list_for_customer(
            customer.id,
        )
    return [address_response(address) for address in addresses]


@router.post("/by-telegram/{telegram_id}/addresses", status_code=201)
async def create_address(
    telegram_id: int,
    request: CreateAddressRequest,
    container: Annotated[Container, Depends(get_container)],
) -> AddressResponse:
    async with container.session_factory() as session:
        address = await CreateCustomerAddressUseCase(
            SqlAlchemyCustomerRepository(session),
            SqlAlchemyAddressRepository(session),
            _geocoder(container),
        ).execute(
            CreateOwnerAddressCommand(
                telegram_id=telegram_id,
                city_id=request.city_id,
                unrestricted_value=request.unrestricted_value,
                entrance=request.entrance,
                floor=request.floor,
                apartment=request.apartment,
                comment=request.comment,
            ),
        )
        await session.commit()
    return address_response(address)


@router.delete("/by-telegram/{telegram_id}/addresses/{address_id}")
async def delete_address(
    telegram_id: int,
    address_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, str]:
    async with container.session_factory() as session:
        await DeleteCustomerAddressUseCase(
            SqlAlchemyCustomerRepository(session),
            SqlAlchemyAddressRepository(session),
        ).execute(telegram_id=telegram_id, address_id=address_id)
        await session.commit()
    return {"status": "deleted"}

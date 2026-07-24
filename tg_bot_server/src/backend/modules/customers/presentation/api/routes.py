from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key
from backend.modules.addresses.application import (
    CreateOwnerAddressCommand,
)
from backend.modules.care_objects.application import (
    CreateCustomerCareObjectCommand,
    UpdateCustomerCareObjectCommand,
)
from backend.modules.customers.application import UpdateCustomerProfileCommand

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
    UpdateCustomerProfileRequest,
    UpdateTelegramUsernameRequest,
)

router = APIRouter(
    prefix="/api/customers",
    tags=["customers"],
    dependencies=[Depends(require_service_key)],
)


@router.get("/by-telegram/{telegram_id}/profile")
async def get_profile(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> CustomerResponse:
    customer = await container.customers.get_customer_profile(telegram_id)
    return customer_response(customer)


@router.post("/register", status_code=201)
async def register(
    request: RegisterCustomerRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CustomerResponse:
    customer = await container.customers.register_customer(
        register_customer_command(request),
    )
    return customer_response(customer)


@router.patch("/by-telegram/{telegram_id}/telegram-username")
async def update_telegram_username(
    telegram_id: int,
    request: UpdateTelegramUsernameRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CustomerResponse:
    customer = await container.customers.update_customer_username(
        update_customer_username_command(telegram_id, request),
    )
    return customer_response(customer)


@router.patch("/by-telegram/{telegram_id}/profile")
async def update_profile(
    telegram_id: int,
    request: UpdateCustomerProfileRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CustomerResponse:
    customer = await container.customers.update_customer_profile(
        UpdateCustomerProfileCommand(
            telegram_id=telegram_id,
            full_name=request.full_name,
            phone=request.phone,
            city_id=request.city_id,
            contact_method=request.contact_method,
        ),
    )
    return customer_response(customer)


@router.get("/by-telegram/{telegram_id}/care-objects")
async def list_care_objects(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
    object_type: Annotated[str | None, Query()] = None,
) -> list[CareObjectResponse]:
    care_objects = await container.customers.list_customer_care_objects(
        telegram_id=telegram_id,
        object_type=object_type,
    )
    return [care_object_response(care_object) for care_object in care_objects]


@router.post("/by-telegram/{telegram_id}/care-objects", status_code=201)
async def create_care_object(
    telegram_id: int,
    request: CreateCareObjectRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CareObjectResponse:
    care_object = await container.customers.create_customer_care_object(
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
    return care_object_response(care_object)


@router.patch("/by-telegram/{telegram_id}/care-objects/{care_object_id}")
async def update_care_object(
    telegram_id: int,
    care_object_id: UUID,
    request: CareObjectRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CareObjectResponse:
    care_object = await container.customers.update_customer_care_object(
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
    return care_object_response(care_object)


@router.delete("/by-telegram/{telegram_id}/care-objects/{care_object_id}")
async def delete_care_object(
    telegram_id: int,
    care_object_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, str]:
    await container.customers.delete_customer_care_object(
        telegram_id=telegram_id,
        care_object_id=care_object_id,
    )
    return {"status": "deleted"}

@router.get("/by-telegram/{telegram_id}/addresses")
async def list_addresses(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> list[AddressResponse]:
    addresses = await container.customers.list_customer_addresses(
        telegram_id=telegram_id,
    )
    return [address_response(address) for address in addresses]


@router.post("/by-telegram/{telegram_id}/addresses", status_code=201)
async def create_address(
    telegram_id: int,
    request: CreateAddressRequest,
    container: Annotated[Container, Depends(get_container)],
) -> AddressResponse:
    address = await container.customers.create_customer_address(
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
    return address_response(address)


@router.delete("/by-telegram/{telegram_id}/addresses/{address_id}")
async def delete_address(
    telegram_id: int,
    address_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, str]:
    await container.customers.delete_customer_address(
        telegram_id=telegram_id,
        address_id=address_id,
    )
    return {"status": "deleted"}

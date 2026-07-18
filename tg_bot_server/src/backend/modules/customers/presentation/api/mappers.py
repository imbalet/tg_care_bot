from backend.modules.addresses.application import AddressDTO
from backend.modules.care_objects.application import CareObjectDTO
from backend.modules.customers.application import (
    RegisterCustomerCommand,
    UpdateCustomerUsernameCommand,
)
from backend.modules.customers.application.dto import CustomerDTO

from .schemas import (
    AddressResponse,
    CareObjectResponse,
    CustomerResponse,
    RegisterCustomerRequest,
    UpdateTelegramUsernameRequest,
)


def register_customer_command(
    request: RegisterCustomerRequest,
) -> RegisterCustomerCommand:
    return RegisterCustomerCommand(
        telegram_id=request.telegram_id,
        full_name=request.full_name,
        phone=request.phone,
        city_id=request.city_id,
        contact_method=request.contact_method,
        telegram_username=request.telegram_username,
        accepted_legal_document_ids=tuple(request.accepted_legal_document_ids),
    )


def update_customer_username_command(
    telegram_id: int,
    request: UpdateTelegramUsernameRequest,
) -> UpdateCustomerUsernameCommand:
    return UpdateCustomerUsernameCommand(
        telegram_id=telegram_id,
        telegram_username=request.telegram_username,
    )


def customer_response(customer: CustomerDTO) -> CustomerResponse:
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


def care_object_response(care_object: CareObjectDTO) -> CareObjectResponse:
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


def address_response(address: AddressDTO) -> AddressResponse:
    return AddressResponse(
        id=str(address.id),
        owner_type=address.owner_type,
        customer_id=str(address.customer_id)
        if address.customer_id is not None
        else None,
        performer_id=str(address.performer_id)
        if address.performer_id is not None
        else None,
        city_id=str(address.city_id),
        district_id=str(address.district_id)
        if address.district_id is not None
        else None,
        address_text=address.address_text,
        fias_id=address.fias_id,
        latitude=str(address.latitude) if address.latitude is not None else None,
        longitude=str(address.longitude) if address.longitude is not None else None,
        geocoding_provider=address.geocoding_provider,
        geocoding_quality=address.geocoding_quality,
        entrance=address.entrance,
        floor=address.floor,
        apartment=address.apartment,
        comment=address.comment,
        deleted_at=address.deleted_at.isoformat()
        if address.deleted_at is not None
        else None,
        created_at=address.created_at.isoformat(),
        updated_at=address.updated_at.isoformat(),
    )

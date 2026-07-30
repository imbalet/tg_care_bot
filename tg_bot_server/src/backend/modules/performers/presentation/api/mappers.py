from backend.modules.addresses.application import AddressDTO
from backend.modules.files.application import FileDTO
from backend.modules.performers.application import (
    InvitationDTO,
    PerformerDTO,
    PerformerServiceDTO,
    RegistrationStateDTO,
)

from .schemas import (
    AddressResponse,
    FileResponse,
    InvitationResponse,
    PerformerResponse,
    PerformerServiceResponse,
    RegistrationStateResponse,
)


def registration_state_response(
    state: RegistrationStateDTO,
) -> RegistrationStateResponse:
    return RegistrationStateResponse(
        state=state.state,
        invitation=invitation_response(state.invitation)
        if state.invitation is not None
        else None,
        performer=performer_response(state.performer)
        if state.performer is not None
        else None,
    )


def invitation_response(invitation: InvitationDTO) -> InvitationResponse:
    return InvitationResponse(
        id=str(invitation.id),
        telegram_id=invitation.telegram_id,
        status=invitation.status,
        expires_at=invitation.expires_at.isoformat()
        if invitation.expires_at is not None
        else None,
        accepted_performer_id=str(invitation.accepted_performer_id)
        if invitation.accepted_performer_id is not None
        else None,
    )


def performer_response(performer: PerformerDTO) -> PerformerResponse:
    return PerformerResponse(
        id=str(performer.id),
        telegram_id=performer.telegram_id,
        full_name=performer.full_name,
        phone=performer.phone,
        telegram_username=performer.telegram_username,
        contact_method=performer.contact_method,
        city_id=str(performer.city_id),
        about_text=performer.about_text,
        status=performer.status,
        is_accepting_orders=performer.is_accepting_orders,
        current_address_id=str(performer.current_address_id)
        if performer.current_address_id is not None
        else None,
        avatar_url=getattr(performer, "avatar_url", None),
    )


def performer_service_response(
    service: PerformerServiceDTO,
) -> PerformerServiceResponse:
    return PerformerServiceResponse(
        id=str(service.id),
        performer_id=str(service.performer_id),
        service_id=str(service.service_id),
        service_code=service.service_code,
        service_name=service.service_name,
        service_location_policy=service.service_location_policy,
        is_approved=service.is_approved,
        is_enabled=service.is_enabled,
        admin_max_objects=service.admin_max_objects,
        performer_max_objects=service.performer_max_objects,
        constraints=service.constraints,
        approved_by_admin_id=str(service.approved_by_admin_id)
        if service.approved_by_admin_id is not None
        else None,
        approved_at=service.approved_at.isoformat()
        if service.approved_at is not None
        else None,
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


def file_response(file: FileDTO) -> FileResponse:
    return FileResponse(
        id=str(file.id),
        bucket=file.bucket,
        storage_key=file.storage_key,
        mime_type=file.mime_type,
        size_bytes=file.size_bytes,
        checksum=file.checksum,
        status=file.status,
    )

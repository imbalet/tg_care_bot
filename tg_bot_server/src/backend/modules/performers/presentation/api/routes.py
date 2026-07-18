from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key
from backend.modules.addresses.application import (
    CreateOwnerAddressCommand,
)
from backend.modules.admin.presentation.api.routes import (
    get_current_admin,
    require_admin_csrf,
)
from backend.modules.admin.presentation.api.schemas import AdminResponse
from backend.modules.availability.application import (
    AddCalendarOverrideCommand,
    SetPerformerScheduleCommand,
)
from backend.modules.availability.presentation.api.mappers import (
    override_response,
    schedule_response,
)
from backend.modules.availability.presentation.api.schemas import (
    AddOverrideRequest,
    CalendarOverrideResponse,
    ScheduleResponse,
    SetScheduleRequest,
)
from backend.modules.files.application import (
    UploadPerformerAvatarCommand,
)
from backend.modules.performers.application import (
    ApprovePerformerServiceCommand,
    CreateInvitationCommand,
    RegisterPerformerCommand,
    SetPerformerAcceptingOrdersCommand,
    SetPerformerServiceEnabledCommand,
    SetPerformerServiceMaxObjectsCommand,
    UpdatePerformerUsernameCommand,
)

from .mappers import (
    address_response,
    file_response,
    invitation_response,
    performer_response,
    performer_service_response,
    registration_state_response,
)
from .schemas import (
    AddressResponse,
    ApprovePerformerServiceRequest,
    CreateAddressRequest,
    CreateInvitationRequest,
    FileResponse,
    InvitationResponse,
    PerformerResponse,
    PerformerServiceResponse,
    RegisterPerformerRequest,
    RegistrationStateResponse,
    SetAcceptingOrdersRequest,
    SetPerformerServiceEnabledRequest,
    SetPerformerServiceMaxObjectsRequest,
    UpdateTelegramUsernameRequest,
)

router = APIRouter(
    prefix="/api",
    tags=["performers"],
    dependencies=[Depends(require_service_key)],
)
admin_router = APIRouter(prefix="/admin/performers", tags=["admin-performers"])


@router.post("/admin/performer-invitations", status_code=201)
async def create_invitation(
    request: CreateInvitationRequest,
    container: Annotated[Container, Depends(get_container)],
) -> InvitationResponse:
    invitation = await container.services().create_invitation(
        CreateInvitationCommand(
            telegram_id=request.telegram_id,
            created_by_admin_id=request.created_by_admin_id,
            expires_at=request.expires_at,
        ),
    )
    return invitation_response(invitation)


@admin_router.post("/invitations", status_code=201)
async def create_invitation_as_admin(
    request: CreateInvitationRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> InvitationResponse:
    admin_id = UUID(current[0].id)
    invitation = await container.services().create_invitation(
        CreateInvitationCommand(
            telegram_id=request.telegram_id,
            created_by_admin_id=admin_id,
            expires_at=request.expires_at,
        ),
        audit_admin_id=admin_id,
    )
    return invitation_response(invitation)


@router.get("/performers/by-telegram/{telegram_id}/registration-state")
async def registration_state(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> RegistrationStateResponse:
    state = await container.services().get_registration_state(telegram_id)
    return registration_state_response(state)


@router.post("/performers/register-by-invitation", status_code=201)
async def register_by_invitation(
    request: RegisterPerformerRequest,
    container: Annotated[Container, Depends(get_container)],
) -> PerformerResponse:
    performer = await container.services().register_performer(
        RegisterPerformerCommand(
            telegram_id=request.telegram_id,
            full_name=request.full_name,
            phone=request.phone,
            city_id=request.city_id,
            contact_method=request.contact_method,
            about_text=request.about_text,
            telegram_username=request.telegram_username,
            accepted_legal_document_ids=tuple(request.accepted_legal_document_ids),
        ),
    )
    return performer_response(performer)


@router.post("/admin/performers/{performer_id}/activate")
async def activate(
    performer_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> PerformerResponse:
    performer = await container.services().activate_performer(performer_id)
    return performer_response(performer)


@admin_router.post("/{performer_id}/activate")
async def activate_as_admin(
    performer_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> PerformerResponse:
    admin_id = UUID(current[0].id)
    performer = await container.services().activate_performer(
        performer_id,
        audit_admin_id=admin_id,
    )
    return performer_response(performer)


@admin_router.post("/{performer_id}/services/{service_id}/approve")
async def approve_service_as_admin(
    performer_id: UUID,
    service_id: UUID,
    request: ApprovePerformerServiceRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> PerformerServiceResponse:
    admin_id = UUID(current[0].id)
    service = await container.services().approve_performer_service(
        ApprovePerformerServiceCommand(
            performer_id=performer_id,
            service_id=service_id,
            admin_max_objects=request.admin_max_objects,
            constraints=request.constraints,
            approved_by_admin_id=admin_id,
        ),
        audit_admin_id=admin_id,
    )
    return performer_service_response(service)


@admin_router.get("/{performer_id}/services")
async def list_services_as_admin(
    performer_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    _current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
) -> list[PerformerServiceResponse]:
    services = await container.services().list_performer_services_by_id(performer_id)
    return [performer_service_response(service) for service in services]


@admin_router.patch("/{performer_id}/schedule")
async def set_schedule_as_admin(
    performer_id: UUID,
    request: SetScheduleRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> ScheduleResponse:
    admin_id = UUID(current[0].id)
    schedule = await container.services().set_schedule_as_admin(
        performer_id,
        lambda telegram_id: SetPerformerScheduleCommand(
            telegram_id=telegram_id,
            schedule_type=request.schedule_type,
            work_days=tuple(request.work_days)
            if request.work_days is not None
            else None,
            work_start_time=request.work_start_time,
            work_end_time=request.work_end_time,
        ),
        audit_admin_id=admin_id,
    )
    return schedule_response(schedule)


@admin_router.post("/{performer_id}/calendar-overrides", status_code=201)
async def add_override_as_admin(
    performer_id: UUID,
    request: AddOverrideRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> CalendarOverrideResponse:
    admin_id = UUID(current[0].id)
    override = await container.services().add_override_as_admin(
        performer_id,
        lambda telegram_id: AddCalendarOverrideCommand(
            telegram_id=telegram_id,
            override_type=request.override_type,
            starts_at=request.starts_at,
            ends_at=request.ends_at,
            comment=request.comment,
        ),
        audit_admin_id=admin_id,
    )
    return override_response(override)


@router.patch("/performers/by-telegram/{telegram_id}/telegram-username")
async def update_telegram_username(
    telegram_id: int,
    request: UpdateTelegramUsernameRequest,
    container: Annotated[Container, Depends(get_container)],
) -> PerformerResponse:
    performer = await container.services().update_performer_username(
        UpdatePerformerUsernameCommand(
            telegram_id=telegram_id,
            telegram_username=request.telegram_username,
        ),
    )
    return performer_response(performer)


@router.get("/performers/by-telegram/{telegram_id}/services")
async def list_services_by_telegram(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> list[PerformerServiceResponse]:
    services = await container.services().list_performer_services_by_telegram(
        telegram_id,
    )
    return [performer_service_response(service) for service in services]


@router.patch("/performers/by-telegram/{telegram_id}/services/{service_id}/enabled")
async def set_service_enabled(
    telegram_id: int,
    service_id: UUID,
    request: SetPerformerServiceEnabledRequest,
    container: Annotated[Container, Depends(get_container)],
) -> PerformerServiceResponse:
    service = await container.services().set_performer_service_enabled(
        SetPerformerServiceEnabledCommand(
            telegram_id=telegram_id,
            service_id=service_id,
            is_enabled=request.is_enabled,
        ),
    )
    return performer_service_response(service)


@router.patch("/performers/by-telegram/{telegram_id}/services/{service_id}/max-objects")
async def set_service_max_objects(
    telegram_id: int,
    service_id: UUID,
    request: SetPerformerServiceMaxObjectsRequest,
    container: Annotated[Container, Depends(get_container)],
) -> PerformerServiceResponse:
    service = await container.services().set_performer_service_max_objects(
        SetPerformerServiceMaxObjectsCommand(
            telegram_id=telegram_id,
            service_id=service_id,
            performer_max_objects=request.performer_max_objects,
        ),
    )
    return performer_service_response(service)


@router.patch("/performers/by-telegram/{telegram_id}/accepting-orders")
async def set_accepting_orders(
    telegram_id: int,
    request: SetAcceptingOrdersRequest,
    container: Annotated[Container, Depends(get_container)],
) -> PerformerResponse:
    performer = await container.services().set_performer_accepting_orders(
        SetPerformerAcceptingOrdersCommand(
            telegram_id=telegram_id,
            is_accepting_orders=request.is_accepting_orders,
        ),
    )
    return performer_response(performer)


@router.get("/performers/by-telegram/{telegram_id}/addresses")
async def list_addresses(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> list[AddressResponse]:
    addresses = await container.services().list_performer_addresses(
        telegram_id=telegram_id,
    )
    return [address_response(address) for address in addresses]


@router.post("/performers/by-telegram/{telegram_id}/addresses", status_code=201)
async def create_address(
    telegram_id: int,
    request: CreateAddressRequest,
    container: Annotated[Container, Depends(get_container)],
) -> AddressResponse:
    address = await container.services().create_performer_address(
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


@router.patch("/performers/by-telegram/{telegram_id}/current-address/{address_id}")
async def set_current_address(
    telegram_id: int,
    address_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> AddressResponse:
    address = await container.services().set_performer_current_address(
        telegram_id=telegram_id,
        address_id=address_id,
    )
    return address_response(address)


@router.delete("/performers/by-telegram/{telegram_id}/addresses/{address_id}")
async def delete_address(
    telegram_id: int,
    address_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, str]:
    await container.services().delete_performer_address(
        telegram_id=telegram_id,
        address_id=address_id,
    )
    return {"status": "deleted"}


@router.post("/performers/by-telegram/{telegram_id}/avatar", status_code=201)
async def upload_avatar(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
    file: Annotated[UploadFile, File()],
) -> FileResponse:
    content = await file.read()
    stored_file = await container.services().upload_performer_avatar(
        UploadPerformerAvatarCommand(
            telegram_id=telegram_id,
            content=content,
            content_type=file.content_type or "",
            original_name=file.filename,
            telegram_file_id=None,
        ),
    )
    return file_response(stored_file)


@router.delete("/performers/by-telegram/{telegram_id}/avatar")
async def delete_avatar(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, str]:
    await container.services().delete_performer_avatar(telegram_id=telegram_id)
    return {"status": "deleted"}

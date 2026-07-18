from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.domain import NotFoundError
from backend.common.infrastructure import S3ObjectStorage
from backend.common.presentation import require_service_key
from backend.modules.addresses.application import (
    CreateOwnerAddressCommand,
    CreatePerformerAddressUseCase,
    DeletePerformerAddressUseCase,
    SetPerformerCurrentAddressUseCase,
)
from backend.modules.addresses.infrastructure import SqlAlchemyAddressRepository
from backend.modules.admin.infrastructure import SqlAlchemyAdminAuditRepository
from backend.modules.admin.presentation.api.routes import (
    get_current_admin,
    require_admin_csrf,
)
from backend.modules.admin.presentation.api.schemas import AdminResponse
from backend.modules.files.application import (
    UploadPerformerAvatarCommand,
    UploadPerformerAvatarUseCase,
)
from backend.modules.files.infrastructure import SqlAlchemyFileRepository
from backend.modules.geo.infrastructure import DaDataGeocoder
from backend.modules.performers.application import (
    ActivatePerformerUseCase,
    ApprovePerformerServiceCommand,
    ApprovePerformerServiceUseCase,
    CreateInvitationCommand,
    CreateInvitationUseCase,
    GetRegistrationStateUseCase,
    ListPerformerServicesUseCase,
    RegisterPerformerCommand,
    RegisterPerformerUseCase,
    SetPerformerAcceptingOrdersCommand,
    SetPerformerAcceptingOrdersUseCase,
    SetPerformerServiceEnabledCommand,
    SetPerformerServiceEnabledUseCase,
    SetPerformerServiceMaxObjectsCommand,
    SetPerformerServiceMaxObjectsUseCase,
    UpdatePerformerUsernameCommand,
    UpdatePerformerUsernameUseCase,
)
from backend.modules.performers.infrastructure import SqlAlchemyPerformerRepository

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
    async with container.session_factory() as session:
        invitation = await CreateInvitationUseCase(
            SqlAlchemyPerformerRepository(session),
        ).execute(
            CreateInvitationCommand(
                telegram_id=request.telegram_id,
                created_by_admin_id=request.created_by_admin_id,
                expires_at=request.expires_at,
            ),
        )
        await session.commit()
    return invitation_response(invitation)


@admin_router.post("/invitations", status_code=201)
async def create_invitation_as_admin(
    request: CreateInvitationRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> InvitationResponse:
    admin_id = UUID(current[0].id)
    async with container.session_factory() as session:
        invitation = await CreateInvitationUseCase(
            SqlAlchemyPerformerRepository(session),
        ).execute(
            CreateInvitationCommand(
                telegram_id=request.telegram_id,
                created_by_admin_id=admin_id,
                expires_at=request.expires_at,
            ),
        )
        await SqlAlchemyAdminAuditRepository(session).add(
            admin_id=admin_id,
            action="create_performer_invitation",
            entity_type="performer_invitation",
            entity_id=invitation.id,
            audit_metadata={"telegram_id": request.telegram_id},
        )
        await session.commit()
    return invitation_response(invitation)


@router.get("/performers/by-telegram/{telegram_id}/registration-state")
async def registration_state(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> RegistrationStateResponse:
    async with container.session_factory() as session:
        state = await GetRegistrationStateUseCase(
            SqlAlchemyPerformerRepository(session),
        ).execute(telegram_id)
        await session.commit()
    return registration_state_response(state)


@router.post("/performers/register-by-invitation", status_code=201)
async def register_by_invitation(
    request: RegisterPerformerRequest,
    container: Annotated[Container, Depends(get_container)],
) -> PerformerResponse:
    async with container.session_factory() as session:
        performer = await RegisterPerformerUseCase(
            SqlAlchemyPerformerRepository(session),
        ).execute(
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
        await session.commit()
    return performer_response(performer)


@router.post("/admin/performers/{performer_id}/activate")
async def activate(
    performer_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> PerformerResponse:
    async with container.session_factory() as session:
        performer = await ActivatePerformerUseCase(
            SqlAlchemyPerformerRepository(session),
        ).execute(performer_id)
        await session.commit()
    return performer_response(performer)


@admin_router.post("/{performer_id}/activate")
async def activate_as_admin(
    performer_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> PerformerResponse:
    admin_id = UUID(current[0].id)
    async with container.session_factory() as session:
        performer = await ActivatePerformerUseCase(
            SqlAlchemyPerformerRepository(session),
        ).execute(performer_id)
        await SqlAlchemyAdminAuditRepository(session).add(
            admin_id=admin_id,
            action="activate_performer",
            entity_type="performer",
            entity_id=performer.id,
        )
        await session.commit()
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
    async with container.session_factory() as session:
        service = await ApprovePerformerServiceUseCase(
            SqlAlchemyPerformerRepository(session),
        ).execute(
            ApprovePerformerServiceCommand(
                performer_id=performer_id,
                service_id=service_id,
                admin_max_objects=request.admin_max_objects,
                constraints=request.constraints,
                approved_by_admin_id=admin_id,
            ),
        )
        await SqlAlchemyAdminAuditRepository(session).add(
            admin_id=admin_id,
            action="approve_performer_service",
            entity_type="performer_service",
            entity_id=service.id,
            audit_metadata={
                "performer_id": str(performer_id),
                "service_id": str(service_id),
                "admin_max_objects": request.admin_max_objects,
            },
        )
        await session.commit()
    return performer_service_response(service)


@admin_router.get("/{performer_id}/services")
async def list_services_as_admin(
    performer_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    _current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
) -> list[PerformerServiceResponse]:
    async with container.session_factory() as session:
        services = await ListPerformerServicesUseCase(
            SqlAlchemyPerformerRepository(session),
        ).execute_for_performer(performer_id)
    return [performer_service_response(service) for service in services]


@router.patch("/performers/by-telegram/{telegram_id}/telegram-username")
async def update_telegram_username(
    telegram_id: int,
    request: UpdateTelegramUsernameRequest,
    container: Annotated[Container, Depends(get_container)],
) -> PerformerResponse:
    async with container.session_factory() as session:
        performer = await UpdatePerformerUsernameUseCase(
            SqlAlchemyPerformerRepository(session),
        ).execute(
            UpdatePerformerUsernameCommand(
                telegram_id=telegram_id,
                telegram_username=request.telegram_username,
            ),
        )
        await session.commit()
    return performer_response(performer)


@router.get("/performers/by-telegram/{telegram_id}/services")
async def list_services_by_telegram(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> list[PerformerServiceResponse]:
    async with container.session_factory() as session:
        services = await ListPerformerServicesUseCase(
            SqlAlchemyPerformerRepository(session),
        ).execute_by_telegram_id(telegram_id)
    return [performer_service_response(service) for service in services]


@router.patch("/performers/by-telegram/{telegram_id}/services/{service_id}/enabled")
async def set_service_enabled(
    telegram_id: int,
    service_id: UUID,
    request: SetPerformerServiceEnabledRequest,
    container: Annotated[Container, Depends(get_container)],
) -> PerformerServiceResponse:
    async with container.session_factory() as session:
        service = await SetPerformerServiceEnabledUseCase(
            SqlAlchemyPerformerRepository(session),
        ).execute(
            SetPerformerServiceEnabledCommand(
                telegram_id=telegram_id,
                service_id=service_id,
                is_enabled=request.is_enabled,
            ),
        )
        await session.commit()
    return performer_service_response(service)


@router.patch("/performers/by-telegram/{telegram_id}/services/{service_id}/max-objects")
async def set_service_max_objects(
    telegram_id: int,
    service_id: UUID,
    request: SetPerformerServiceMaxObjectsRequest,
    container: Annotated[Container, Depends(get_container)],
) -> PerformerServiceResponse:
    async with container.session_factory() as session:
        service = await SetPerformerServiceMaxObjectsUseCase(
            SqlAlchemyPerformerRepository(session),
        ).execute(
            SetPerformerServiceMaxObjectsCommand(
                telegram_id=telegram_id,
                service_id=service_id,
                performer_max_objects=request.performer_max_objects,
            ),
        )
        await session.commit()
    return performer_service_response(service)


@router.patch("/performers/by-telegram/{telegram_id}/accepting-orders")
async def set_accepting_orders(
    telegram_id: int,
    request: SetAcceptingOrdersRequest,
    container: Annotated[Container, Depends(get_container)],
) -> PerformerResponse:
    async with container.session_factory() as session:
        performer = await SetPerformerAcceptingOrdersUseCase(
            SqlAlchemyPerformerRepository(session),
        ).execute(
            SetPerformerAcceptingOrdersCommand(
                telegram_id=telegram_id,
                is_accepting_orders=request.is_accepting_orders,
            ),
        )
        await session.commit()
    return performer_response(performer)


@router.get("/performers/by-telegram/{telegram_id}/addresses")
async def list_addresses(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> list[AddressResponse]:
    async with container.session_factory() as session:
        performer = await SqlAlchemyPerformerRepository(
            session,
        ).get_performer_by_telegram_id(telegram_id)
        if performer is None:
            raise NotFoundError("Performer is not registered")
        addresses = await SqlAlchemyAddressRepository(session).list_for_performer(
            performer.id,
        )
    return [address_response(address) for address in addresses]


@router.post("/performers/by-telegram/{telegram_id}/addresses", status_code=201)
async def create_address(
    telegram_id: int,
    request: CreateAddressRequest,
    container: Annotated[Container, Depends(get_container)],
) -> AddressResponse:
    async with container.session_factory() as session:
        address = await CreatePerformerAddressUseCase(
            SqlAlchemyPerformerRepository(session),
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


@router.patch("/performers/by-telegram/{telegram_id}/current-address/{address_id}")
async def set_current_address(
    telegram_id: int,
    address_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> AddressResponse:
    async with container.session_factory() as session:
        address = await SetPerformerCurrentAddressUseCase(
            SqlAlchemyPerformerRepository(session),
            SqlAlchemyAddressRepository(session),
        ).execute(telegram_id=telegram_id, address_id=address_id)
        await session.commit()
    return address_response(address)


@router.delete("/performers/by-telegram/{telegram_id}/addresses/{address_id}")
async def delete_address(
    telegram_id: int,
    address_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, str]:
    async with container.session_factory() as session:
        await DeletePerformerAddressUseCase(
            SqlAlchemyPerformerRepository(session),
            SqlAlchemyAddressRepository(session),
        ).execute(telegram_id=telegram_id, address_id=address_id)
        await session.commit()
    return {"status": "deleted"}


@router.post("/performers/by-telegram/{telegram_id}/avatar", status_code=201)
async def upload_avatar(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
    file: Annotated[UploadFile, File()],
) -> FileResponse:
    content = await file.read()
    async with container.session_factory() as session:
        stored_file = await UploadPerformerAvatarUseCase(
            SqlAlchemyPerformerRepository(session),
            SqlAlchemyFileRepository(session),
            _storage(container),
        ).execute(
            UploadPerformerAvatarCommand(
                telegram_id=telegram_id,
                content=content,
                content_type=file.content_type or "",
                original_name=file.filename,
                telegram_file_id=None,
            ),
        )
        await session.commit()
    return file_response(stored_file)


@router.delete("/performers/by-telegram/{telegram_id}/avatar")
async def delete_avatar(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, str]:
    async with container.session_factory() as session:
        performer = await SqlAlchemyPerformerRepository(
            session,
        ).get_performer_by_telegram_id(telegram_id)
        if performer is None:
            raise NotFoundError("Performer is not registered")
        file_repository = SqlAlchemyFileRepository(session)
        avatar = await file_repository.get_avatar_for_entity(
            entity_type="performer",
            entity_id=performer.id,
        )
        if avatar is None:
            raise NotFoundError("Avatar not found")
        if avatar.storage_key is not None:
            await _storage(container).delete(avatar.storage_key)
        await file_repository.delete_avatar_link(
            entity_type="performer",
            entity_id=performer.id,
        )
        await file_repository.mark_deleted(avatar.id)
        await session.commit()
    return {"status": "deleted"}


def _geocoder(container: Container) -> DaDataGeocoder:
    settings = container.settings
    return DaDataGeocoder(
        api_key=settings.dadata_api_key,
        secret_key=settings.dadata_secret_key,
        base_url=settings.dadata_base_url,
        timeout_seconds=settings.dadata_timeout_seconds,
        retry_count=settings.dadata_retry_count,
    )


def _storage(container: Container) -> S3ObjectStorage:
    settings = container.settings
    return S3ObjectStorage(
        endpoint_url=settings.s3_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
        bucket=settings.s3_bucket,
        region=settings.s3_region,
        signed_url_ttl_seconds=settings.s3_signed_url_ttl_seconds,
    )

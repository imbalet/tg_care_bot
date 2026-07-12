from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.domain import NotFoundError
from backend.common.infrastructure import S3ObjectStorage
from backend.common.presentation import require_service_key
from backend.modules.addresses.application import (
    AddressDTO,
    CreateOwnerAddressCommand,
    CreatePerformerAddressUseCase,
    DeletePerformerAddressUseCase,
    SetPerformerCurrentAddressUseCase,
)
from backend.modules.addresses.infrastructure import SqlAlchemyAddressRepository
from backend.modules.admin.infrastructure import SqlAlchemyAdminAuditRepository
from backend.modules.admin.presentation.api.routes import (
    AdminResponse,
    require_admin_csrf,
)
from backend.modules.files.application import (
    UploadPerformerAvatarCommand,
    UploadPerformerAvatarUseCase,
)
from backend.modules.files.infrastructure import SqlAlchemyFileRepository
from backend.modules.geo.infrastructure import DaDataGeocoder
from backend.modules.performers.application import (
    ActivatePerformerUseCase,
    CreateInvitationCommand,
    CreateInvitationUseCase,
    GetRegistrationStateUseCase,
    InvitationDTO,
    PerformerDTO,
    RegisterPerformerCommand,
    RegisterPerformerUseCase,
    RegistrationStateDTO,
    UpdatePerformerUsernameCommand,
    UpdatePerformerUsernameUseCase,
)
from backend.modules.performers.infrastructure import SqlAlchemyPerformerRepository

router = APIRouter(
    prefix="/api",
    tags=["performers"],
    dependencies=[Depends(require_service_key)],
)
admin_router = APIRouter(prefix="/admin/performers", tags=["admin-performers"])


class CreateInvitationRequest(BaseModel):
    telegram_id: int
    created_by_admin_id: UUID
    expires_at: datetime | None = None


class RegisterPerformerRequest(BaseModel):
    telegram_id: int
    full_name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    city_id: UUID
    contact_method: str
    about_text: str = Field(min_length=1)
    telegram_username: str | None = None
    accepted_legal_document_ids: list[UUID]


class UpdateTelegramUsernameRequest(BaseModel):
    telegram_username: str | None = None


class CreateAddressRequest(BaseModel):
    city_id: UUID
    unrestricted_value: str = Field(min_length=1)
    entrance: str | None = None
    floor: str | None = None
    apartment: str | None = None
    comment: str | None = None


class AddressResponse(BaseModel):
    id: str
    owner_type: str
    customer_id: str | None
    performer_id: str | None
    city_id: str
    district_id: str | None
    address_text: str
    fias_id: str | None
    latitude: str | None
    longitude: str | None
    geocoding_provider: str | None
    geocoding_quality: str | None
    entrance: str | None
    floor: str | None
    apartment: str | None
    comment: str | None
    deleted_at: str | None
    created_at: str
    updated_at: str


class FileResponse(BaseModel):
    id: str
    bucket: str
    storage_key: str | None
    mime_type: str
    size_bytes: int | None
    checksum: str | None
    status: str


class InvitationResponse(BaseModel):
    id: str
    telegram_id: int
    status: str
    expires_at: str | None
    accepted_performer_id: str | None


class PerformerResponse(BaseModel):
    id: str
    telegram_id: int
    full_name: str
    phone: str
    telegram_username: str | None
    contact_method: str
    city_id: str
    about_text: str | None
    status: str
    is_accepting_orders: bool
    current_address_id: str | None


class RegistrationStateResponse(BaseModel):
    state: str
    invitation: InvitationResponse | None
    performer: PerformerResponse | None


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
    return _invitation_response(invitation)


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
    return _invitation_response(invitation)


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
    return _registration_state_response(state)


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
    return _performer_response(performer)


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
    return _performer_response(performer)


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
    return _performer_response(performer)


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
    return _performer_response(performer)


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
            from backend.common.domain import NotFoundError

            raise NotFoundError("Performer is not registered")
        addresses = await SqlAlchemyAddressRepository(session).list_for_performer(
            performer.id,
        )
    return [_address_response(address) for address in addresses]


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
    return _address_response(address)


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
    return _address_response(address)


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
    return FileResponse(
        id=str(stored_file.id),
        bucket=stored_file.bucket,
        storage_key=stored_file.storage_key,
        mime_type=stored_file.mime_type,
        size_bytes=stored_file.size_bytes,
        checksum=stored_file.checksum,
        status=stored_file.status,
    )


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


def _registration_state_response(
    state: RegistrationStateDTO,
) -> RegistrationStateResponse:
    return RegistrationStateResponse(
        state=state.state,
        invitation=_invitation_response(state.invitation)
        if state.invitation is not None
        else None,
        performer=_performer_response(state.performer)
        if state.performer is not None
        else None,
    )


def _invitation_response(invitation: InvitationDTO) -> InvitationResponse:
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


def _performer_response(performer: PerformerDTO) -> PerformerResponse:
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
    )


def _address_response(address: AddressDTO) -> AddressResponse:
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


__all__ = ["admin_router", "router"]

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key
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
)
from backend.modules.performers.infrastructure import SqlAlchemyPerformerRepository

router = APIRouter(
    prefix="/api",
    tags=["performers"],
    dependencies=[Depends(require_service_key)],
)


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
    )


__all__ = ["router"]

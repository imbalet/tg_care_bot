from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import new_uuid, utc_now
from backend.modules.catalog.infrastructure import CityModel, LegalDocumentModel
from backend.modules.customers.infrastructure import LegalAcceptanceModel
from backend.modules.performers.application.dto import InvitationDTO, PerformerDTO
from backend.modules.performers.infrastructure.persistence.models import (
    PerformerInvitationModel,
    PerformerModel,
)


class SqlAlchemyPerformerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_invitation(
        self,
        *,
        telegram_id: int,
        created_by_admin_id: UUID,
        expires_at: datetime | None,
    ) -> InvitationDTO:
        now = utc_now()
        model = PerformerInvitationModel(
            id=new_uuid(),
            telegram_id=telegram_id,
            created_by_admin_id=created_by_admin_id,
            status="pending",
            expires_at=expires_at,
            accepted_performer_id=None,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        return _invitation_to_dto(model)

    async def get_performer_by_telegram_id(
        self,
        telegram_id: int,
    ) -> PerformerDTO | None:
        result = await self._session.execute(
            select(PerformerModel).where(PerformerModel.telegram_id == telegram_id),
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _performer_to_dto(model)

    async def get_pending_invitation(self, telegram_id: int) -> InvitationDTO | None:
        result = await self._session.execute(
            select(PerformerInvitationModel)
            .where(
                PerformerInvitationModel.telegram_id == telegram_id,
                PerformerInvitationModel.status == "pending",
            )
            .order_by(PerformerInvitationModel.created_at.desc()),
        )
        model = result.scalars().first()
        if model is None:
            return None
        return _invitation_to_dto(model)

    async def mark_invitation_expired(self, invitation_id: UUID) -> None:
        model = await self._session.get(PerformerInvitationModel, invitation_id)
        if model is None:
            return
        now = utc_now()
        model.status = "expired"
        model.updated_at = now

    async def create_performer_from_invitation(
        self,
        *,
        invitation_id: UUID,
        telegram_id: int,
        full_name: str,
        phone: str,
        city_id: UUID,
        contact_method: str,
        about_text: str,
        telegram_username: str | None,
        accepted_legal_document_ids: tuple[UUID, ...],
    ) -> PerformerDTO:
        now = utc_now()
        performer = PerformerModel(
            id=new_uuid(),
            telegram_id=telegram_id,
            full_name=full_name,
            phone=phone,
            telegram_username=telegram_username,
            contact_method=contact_method,
            city_id=city_id,
            about_text=about_text,
            status="profile_pending",
            is_accepting_orders=False,
            current_address_id=None,
            payment_recipient_id=None,
            blocked_reason=None,
            deleted_at=None,
            anonymized_at=None,
            created_at=now,
            updated_at=now,
        )
        self._session.add(performer)
        await self._session.flush()
        invitation = await self._session.get(PerformerInvitationModel, invitation_id)
        if invitation is not None:
            invitation.status = "accepted"
            invitation.accepted_performer_id = performer.id
            invitation.updated_at = now
        for document_id in accepted_legal_document_ids:
            self._session.add(
                LegalAcceptanceModel(
                    id=new_uuid(),
                    account_type="performer",
                    customer_id=None,
                    performer_id=performer.id,
                    document_id=document_id,
                    accepted_at=now,
                    revoked_at=None,
                    created_at=now,
                ),
            )
        return _performer_to_dto(performer)

    async def activate(self, performer_id: UUID) -> PerformerDTO | None:
        model = await self._session.get(PerformerModel, performer_id)
        if model is None:
            return None
        model.status = "active"
        model.updated_at = utc_now()
        return _performer_to_dto(model)

    async def get_city_is_active(self, city_id: UUID) -> bool:
        result = await self._session.execute(
            select(CityModel.is_active).where(CityModel.id == city_id),
        )
        return result.scalar_one_or_none() is True

    async def list_active_legal_document_ids(self) -> tuple[UUID, ...]:
        result = await self._session.execute(
            select(LegalDocumentModel.id).where(LegalDocumentModel.is_active.is_(True)),
        )
        return tuple(result.scalars())


def _performer_to_dto(model: PerformerModel) -> PerformerDTO:
    return PerformerDTO(
        id=model.id,
        telegram_id=model.telegram_id,
        full_name=model.full_name,
        phone=model.phone,
        telegram_username=model.telegram_username,
        contact_method=model.contact_method,
        city_id=model.city_id,
        about_text=model.about_text,
        status=model.status,
        is_accepting_orders=model.is_accepting_orders,
    )


def _invitation_to_dto(model: PerformerInvitationModel) -> InvitationDTO:
    return InvitationDTO(
        id=model.id,
        telegram_id=model.telegram_id,
        status=model.status,
        expires_at=model.expires_at,
        accepted_performer_id=model.accepted_performer_id,
    )


__all__ = ["SqlAlchemyPerformerRepository"]

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import new_uuid, utc_now
from backend.common.domain import ConflictError
from backend.modules.catalog.infrastructure import (
    CityModel,
    LegalDocumentModel,
    ServiceCategoryModel,
    ServiceModel,
)
from backend.modules.customers.infrastructure import LegalAcceptanceModel
from backend.modules.performers.application.dto import (
    InvitationDTO,
    PerformerDTO,
    PerformerServiceDTO,
    PerformerServiceSelection,
    PerformerServicesSyncResult,
)
from backend.modules.performers.application.interfaces import PerformerRepository
from backend.modules.performers.infrastructure.persistence.models import (
    PerformerInvitationModel,
    PerformerModel,
    PerformerServiceModel,
)


class SqlAlchemyPerformerRepository(PerformerRepository):
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
        existing = await self._pending_invitation_model(telegram_id)
        if existing is not None:
            existing.created_by_admin_id = created_by_admin_id
            existing.expires_at = expires_at
            existing.updated_at = now
            await self._session.flush()
            return _invitation_to_dto(existing)
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

    async def get_performer_by_id(self, performer_id: UUID) -> PerformerDTO | None:
        model = await self._session.get(PerformerModel, performer_id)
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

    async def _pending_invitation_model(
        self,
        telegram_id: int,
    ) -> PerformerInvitationModel | None:
        result = await self._session.execute(
            select(PerformerInvitationModel)
            .where(
                PerformerInvitationModel.telegram_id == telegram_id,
                PerformerInvitationModel.status == "pending",
            )
            .order_by(PerformerInvitationModel.created_at.desc())
            .with_for_update(),
        )
        return result.scalars().first()

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
        result = await self._session.execute(
            select(PerformerModel)
            .where(PerformerModel.id == performer_id)
            .with_for_update(),
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        if model.status != "profile_pending":
            raise ConflictError("Only profile-pending performers can be activated")
        model.status = "active"
        model.updated_at = utc_now()
        return _performer_to_dto(model)

    async def update_username(
        self,
        *,
        telegram_id: int,
        telegram_username: str | None,
    ) -> PerformerDTO | None:
        result = await self._session.execute(
            select(PerformerModel).where(PerformerModel.telegram_id == telegram_id),
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        if model.telegram_username != telegram_username:
            model.telegram_username = telegram_username
            model.updated_at = utc_now()
        return _performer_to_dto(model)

    async def update_profile(
        self,
        *,
        telegram_id: int,
        phone: str,
        contact_method: str,
    ) -> PerformerDTO | None:
        result = await self._session.execute(
            select(PerformerModel)
            .where(PerformerModel.telegram_id == telegram_id)
            .with_for_update(),
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        model.phone = phone
        model.contact_method = contact_method
        model.updated_at = utc_now()
        await self._session.flush()
        return _performer_to_dto(model)

    async def set_current_address(
        self,
        *,
        performer_id: UUID,
        address_id: UUID,
    ) -> None:
        model = await self._session.get(PerformerModel, performer_id)
        if model is None:
            return
        model.current_address_id = address_id
        model.updated_at = utc_now()

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

    async def list_services_for_performer(
        self,
        performer_id: UUID,
    ) -> tuple[PerformerServiceDTO, ...]:
        result = await self._session.execute(
            _performer_service_statement().where(
                PerformerServiceModel.performer_id == performer_id,
            ),
        )
        return tuple(_performer_service_to_dto(*row) for row in result.tuples())

    async def list_services_by_telegram_id(
        self,
        telegram_id: int,
    ) -> tuple[PerformerServiceDTO, ...] | None:
        performer = await self._get_performer_model_by_telegram_id(telegram_id)
        if performer is None:
            return None
        return await self.list_services_for_performer(performer.id)

    async def approve_service(
        self,
        *,
        performer_id: UUID,
        service_id: UUID,
        admin_max_objects: int,
        constraints: dict[str, Any],
        approved_by_admin_id: UUID,
    ) -> PerformerServiceDTO | None:
        performer = await self._session.get(PerformerModel, performer_id)
        if performer is None:
            return None
        now = utc_now()
        model = await self._get_performer_service_model(
            performer_id=performer_id,
            service_id=service_id,
        )
        if model is None:
            model = PerformerServiceModel(
                id=new_uuid(),
                performer_id=performer_id,
                service_id=service_id,
                is_approved=True,
                is_enabled=False,
                admin_max_objects=admin_max_objects,
                performer_max_objects=admin_max_objects,
                constraints=constraints,
                approved_by_admin_id=approved_by_admin_id,
                approved_at=now,
                created_at=now,
                updated_at=now,
            )
            self._session.add(model)
        else:
            model.is_approved = True
            model.admin_max_objects = admin_max_objects
            if model.performer_max_objects > admin_max_objects:
                model.performer_max_objects = admin_max_objects
            model.constraints = constraints
            model.approved_by_admin_id = approved_by_admin_id
            model.approved_at = now
            model.updated_at = now
        await self._session.flush()
        return await self._get_performer_service_dto(model.id)

    async def revoke_service(
        self,
        *,
        performer_id: UUID,
        service_id: UUID,
    ) -> PerformerServiceDTO | None:
        model = await self._get_performer_service_model(
            performer_id=performer_id,
            service_id=service_id,
        )
        if model is None:
            return None
        model.is_approved = False
        model.is_enabled = False
        model.approved_by_admin_id = None
        model.approved_at = None
        model.updated_at = utc_now()
        await self._session.flush()
        return await self._get_performer_service_dto(model.id)

    async def sync_services(
        self,
        *,
        performer_id: UUID,
        selections: tuple[PerformerServiceSelection, ...],
        approved_by_admin_id: UUID,
    ) -> PerformerServicesSyncResult | None:
        performer_result = await self._session.execute(
            select(PerformerModel)
            .where(PerformerModel.id == performer_id)
            .with_for_update(),
        )
        if performer_result.scalar_one_or_none() is None:
            return None

        result = await self._session.execute(
            _performer_service_statement()
            .where(PerformerServiceModel.performer_id == performer_id)
            .with_for_update(of=PerformerServiceModel),
        )
        current_rows = list(result.tuples())
        current_by_service_id = {
            model.service_id: (model, service) for model, service in current_rows
        }
        selections_by_service_id = {
            selection.service_id: selection for selection in selections
        }
        added_ids: list[UUID] = []
        revoked_ids: list[UUID] = []
        updated_ids: list[UUID] = []

        for selection in selections:
            current = current_by_service_id.get(selection.service_id)
            if current is None:
                now = utc_now()
                model = PerformerServiceModel(
                    id=new_uuid(),
                    performer_id=performer_id,
                    service_id=selection.service_id,
                    is_approved=True,
                    is_enabled=False,
                    admin_max_objects=selection.admin_max_objects,
                    performer_max_objects=selection.admin_max_objects,
                    constraints=selection.constraints,
                    approved_by_admin_id=approved_by_admin_id,
                    approved_at=now,
                    created_at=now,
                    updated_at=now,
                )
                self._session.add(model)
                added_ids.append(model.id)
                continue

            model, _service = current
            if (
                not model.is_approved
                or model.admin_max_objects != selection.admin_max_objects
                or model.constraints != selection.constraints
            ):
                model.is_approved = True
                model.admin_max_objects = selection.admin_max_objects
                if model.performer_max_objects > selection.admin_max_objects:
                    model.performer_max_objects = selection.admin_max_objects
                model.constraints = selection.constraints
                model.approved_by_admin_id = approved_by_admin_id
                model.approved_at = utc_now()
                model.updated_at = utc_now()
                updated_ids.append(model.id)

        for service_id, (model, _service) in current_by_service_id.items():
            if service_id in selections_by_service_id or not model.is_approved:
                continue
            model.is_approved = False
            model.is_enabled = False
            model.approved_by_admin_id = None
            model.approved_at = None
            model.updated_at = utc_now()
            revoked_ids.append(model.id)

        await self._session.flush()
        services = await self.list_services_for_performer(performer_id)
        by_id = {service.id: service for service in services}
        return PerformerServicesSyncResult(
            services=services,
            added=tuple(by_id[service_id] for service_id in added_ids),
            revoked=tuple(by_id[service_id] for service_id in revoked_ids),
            updated=tuple(by_id[service_id] for service_id in updated_ids),
        )

    async def set_service_enabled_by_telegram_id(
        self,
        *,
        telegram_id: int,
        service_id: UUID,
        is_enabled: bool,
    ) -> PerformerServiceDTO | None:
        performer = await self._get_performer_model_by_telegram_id(telegram_id)
        if performer is None:
            return None
        model = await self._get_performer_service_model(
            performer_id=performer.id,
            service_id=service_id,
        )
        if model is None or not model.is_approved:
            return None
        model.is_enabled = is_enabled
        model.updated_at = utc_now()
        await self._session.flush()
        return await self._get_performer_service_dto(model.id)

    async def set_service_max_objects_by_telegram_id(
        self,
        *,
        telegram_id: int,
        service_id: UUID,
        performer_max_objects: int,
    ) -> PerformerServiceDTO | None:
        performer = await self._get_performer_model_by_telegram_id(telegram_id)
        if performer is None:
            return None
        model = await self._get_performer_service_model(
            performer_id=performer.id,
            service_id=service_id,
        )
        if model is None or not model.is_approved:
            return None
        model.performer_max_objects = performer_max_objects
        model.updated_at = utc_now()
        await self._session.flush()
        return await self._get_performer_service_dto(model.id)

    async def set_accepting_orders_by_telegram_id(
        self,
        *,
        telegram_id: int,
        is_accepting_orders: bool,
    ) -> PerformerDTO | None:
        performer = await self._get_performer_model_by_telegram_id(telegram_id)
        if performer is None or performer.status != "active":
            return None
        performer.is_accepting_orders = is_accepting_orders
        performer.updated_at = utc_now()
        return _performer_to_dto(performer)

    async def set_nearby_order_notifications_by_telegram_id(
        self,
        *,
        telegram_id: int,
        is_enabled: bool,
    ) -> bool | None:
        performer = await self._get_performer_model_by_telegram_id(telegram_id)
        if performer is None or performer.status != "active":
            return None
        performer.is_nearby_order_notifications_enabled = is_enabled
        performer.updated_at = utc_now()
        await self._session.flush()
        return performer.is_nearby_order_notifications_enabled

    async def get_nearby_order_notifications_by_telegram_id(
        self,
        *,
        telegram_id: int,
    ) -> bool | None:
        performer = await self._get_performer_model_by_telegram_id(telegram_id)
        if performer is None or performer.status != "active":
            return None
        return performer.is_nearby_order_notifications_enabled

    async def get_service_order_limit(self, service_id: UUID) -> int | None:
        result = await self._session.execute(
            select(ServiceCategoryModel.max_objects_per_order)
            .join(ServiceModel, ServiceModel.category_id == ServiceCategoryModel.id)
            .where(
                ServiceModel.id == service_id,
                ServiceModel.is_active.is_(True),
                ServiceCategoryModel.is_active.is_(True),
            ),
        )
        return result.scalar_one_or_none()

    async def _get_performer_model_by_telegram_id(
        self,
        telegram_id: int,
    ) -> PerformerModel | None:
        result = await self._session.execute(
            select(PerformerModel).where(PerformerModel.telegram_id == telegram_id),
        )
        return result.scalar_one_or_none()

    async def _get_performer_service_model(
        self,
        *,
        performer_id: UUID,
        service_id: UUID,
    ) -> PerformerServiceModel | None:
        result = await self._session.execute(
            select(PerformerServiceModel).where(
                PerformerServiceModel.performer_id == performer_id,
                PerformerServiceModel.service_id == service_id,
            ),
        )
        return result.scalar_one_or_none()

    async def _get_performer_service_dto(
        self,
        performer_service_id: UUID,
    ) -> PerformerServiceDTO:
        result = await self._session.execute(
            _performer_service_statement().where(
                PerformerServiceModel.id == performer_service_id,
            ),
        )
        row = result.tuples().one()
        return _performer_service_to_dto(*row)


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
        current_address_id=model.current_address_id,
    )


def _invitation_to_dto(model: PerformerInvitationModel) -> InvitationDTO:
    return InvitationDTO(
        id=model.id,
        telegram_id=model.telegram_id,
        status=model.status,
        expires_at=model.expires_at,
        accepted_performer_id=model.accepted_performer_id,
        updated_at=model.updated_at,
    )


def _performer_service_statement() -> Select[
    tuple[PerformerServiceModel, ServiceModel]
]:
    return (
        select(PerformerServiceModel, ServiceModel)
        .join(ServiceModel, ServiceModel.id == PerformerServiceModel.service_id)
        .order_by(ServiceModel.code)
    )


def _performer_service_to_dto(
    model: PerformerServiceModel,
    service: ServiceModel,
) -> PerformerServiceDTO:
    return PerformerServiceDTO(
        id=model.id,
        performer_id=model.performer_id,
        service_id=model.service_id,
        service_code=service.code,
        service_name=service.name,
        service_location_policy=service.location_policy,
        is_approved=model.is_approved,
        is_enabled=model.is_enabled,
        admin_max_objects=model.admin_max_objects,
        performer_max_objects=model.performer_max_objects,
        constraints=model.constraints,
        approved_by_admin_id=model.approved_by_admin_id,
        approved_at=model.approved_at,
    )

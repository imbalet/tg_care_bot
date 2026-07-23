from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import utc_now
from backend.common.domain import NotFoundError
from backend.modules.care_objects.application import (
    CareObjectDTO,
    CareObjectQueryService,
    CareObjectRepository,
    CreateCareObjectCommand,
    UpdateCareObjectCommand,
    validate_care_object_fields,
)
from backend.modules.orders.infrastructure.persistence.models import (
    ACTIVE_ORDER_STATUSES,
    OrderCareObjectModel,
    OrderModel,
)

from .models import CareObjectModel


def _to_dto(model: CareObjectModel) -> CareObjectDTO:
    return CareObjectDTO(
        id=model.id,
        customer_id=model.customer_id,
        object_type=model.object_type,
        display_name=model.display_name,
        age_group=model.age_group,
        species=model.species,
        breed=model.breed,
        pet_size=model.pet_size,
        mobility_assistance_required=model.mobility_assistance_required,
        routine_notes=model.routine_notes,
        behavior_notes=model.behavior_notes,
        deleted_at=model.deleted_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyCareObjectRepository(CareObjectRepository, CareObjectQueryService):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, care_object_id: UUID) -> CareObjectDTO | None:
        model = await self._session.get(CareObjectModel, care_object_id)
        return _to_dto(model) if model is not None else None

    async def add(self, command: CreateCareObjectCommand) -> CareObjectDTO:
        validate_care_object_fields(
            object_type=command.object_type,
            age_group=command.age_group,
            species=command.species,
            breed=command.breed,
            pet_size=command.pet_size,
            mobility_assistance_required=command.mobility_assistance_required,
        )
        model = CareObjectModel(
            customer_id=command.customer_id,
            object_type=command.object_type,
            display_name=command.display_name,
            age_group=command.age_group,
            species=command.species,
            breed=command.breed,
            pet_size=command.pet_size,
            mobility_assistance_required=command.mobility_assistance_required,
            routine_notes=command.routine_notes,
            behavior_notes=command.behavior_notes,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_dto(model)

    async def update(self, command: UpdateCareObjectCommand) -> CareObjectDTO:
        model = await self._session.get(CareObjectModel, command.care_object_id)
        if model is None or model.deleted_at is not None:
            raise NotFoundError("Care object not found")
        validate_care_object_fields(
            object_type=model.object_type,
            age_group=command.age_group,
            species=command.species,
            breed=command.breed,
            pet_size=command.pet_size,
            mobility_assistance_required=command.mobility_assistance_required,
        )
        model.display_name = command.display_name
        model.age_group = command.age_group
        model.species = command.species
        model.breed = command.breed
        model.pet_size = command.pet_size
        model.mobility_assistance_required = command.mobility_assistance_required
        model.routine_notes = command.routine_notes
        model.behavior_notes = command.behavior_notes
        await self._session.flush()
        return _to_dto(model)

    async def soft_delete(self, care_object_id: UUID) -> None:
        model = await self._session.get(CareObjectModel, care_object_id)
        if model is None or model.deleted_at is not None:
            raise NotFoundError("Care object not found")
        model.deleted_at = utc_now()

    async def has_active_order(self, care_object_id: UUID) -> bool:
        care_object = await self._session.scalar(
            select(CareObjectModel)
            .where(CareObjectModel.id == care_object_id)
            .with_for_update(),
        )
        if care_object is None:
            return False
        statement = select(
            exists().where(
                OrderCareObjectModel.care_object_id == care_object_id,
                OrderCareObjectModel.order_id == OrderModel.id,
                OrderModel.status.in_(ACTIVE_ORDER_STATUSES),
            ),
        )
        return bool(await self._session.scalar(statement))

    async def list_for_customer(
        self,
        customer_id: UUID,
        *,
        active_only: bool = True,
        object_type: str | None = None,
    ) -> tuple[CareObjectDTO, ...]:
        statement = select(CareObjectModel).where(
            CareObjectModel.customer_id == customer_id,
        )
        if active_only:
            statement = statement.where(CareObjectModel.deleted_at.is_(None))
        if object_type is not None:
            statement = statement.where(CareObjectModel.object_type == object_type)
        statement = statement.order_by(CareObjectModel.created_at)
        result = await self._session.execute(statement)
        return tuple(_to_dto(model) for model in result.scalars())

from datetime import datetime, time
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import to_timezone, utc_now
from backend.modules.addresses.infrastructure import AddressModel
from backend.modules.availability.application import (
    AvailabilityCheckDTO,
    AvailabilityRepository,
    CalendarOverrideDTO,
    PerformerScheduleDTO,
    SuitablePerformerDTO,
)
from backend.modules.care_objects.infrastructure import CareObjectModel
from backend.modules.catalog.infrastructure import CityModel, ServiceModel
from backend.modules.geo.application import haversine_distance_km
from backend.modules.orders.infrastructure.persistence.models import (
    OrderMatchModel,
    OrderModel,
)
from backend.modules.performers.infrastructure import (
    PerformerCalendarOverrideModel,
    PerformerModel,
    PerformerScheduleModel,
    PerformerServiceModel,
)


class SqlAlchemyAvailabilityRepository(AvailabilityRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def set_schedule(
        self,
        *,
        telegram_id: int,
        schedule_type: str,
        work_days: tuple[int, ...] | None,
        work_start_time: time,
        work_end_time: time,
    ) -> PerformerScheduleDTO | None:
        performer = await self._get_performer_by_telegram_id(telegram_id)
        if performer is None:
            return None
        now = utc_now()
        await self._session.execute(
            update(PerformerScheduleModel)
            .where(
                PerformerScheduleModel.performer_id == performer.id,
                PerformerScheduleModel.is_active.is_(True),
            )
            .values(is_active=False, updated_at=now),
        )
        model = PerformerScheduleModel(
            performer_id=performer.id,
            schedule_type=schedule_type,
            work_days=list(work_days) if work_days is not None else None,
            work_start_time=work_start_time,
            work_end_time=work_end_time,
            is_active=True,
        )
        self._session.add(model)
        await self._session.flush()
        return _schedule_to_dto(model)

    async def get_performer_timezone(self, performer_id: UUID) -> str | None:
        result = await self._session.execute(
            select(CityModel.timezone)
            .join(PerformerModel, PerformerModel.city_id == CityModel.id)
            .where(
                PerformerModel.id == performer_id,
                CityModel.is_active.is_(True),
            ),
        )
        return result.scalar_one_or_none()

    async def get_performer_timezone_by_telegram_id(
        self,
        telegram_id: int,
    ) -> str | None:
        result = await self._session.execute(
            select(CityModel.timezone)
            .join(PerformerModel, PerformerModel.city_id == CityModel.id)
            .where(
                PerformerModel.telegram_id == telegram_id,
                CityModel.is_active.is_(True),
            ),
        )
        return result.scalar_one_or_none()

    async def add_override(
        self,
        *,
        telegram_id: int,
        override_type: str,
        starts_at: datetime,
        ends_at: datetime,
        comment: str | None,
    ) -> CalendarOverrideDTO | None:
        performer = await self._get_performer_by_telegram_id(telegram_id)
        if performer is None:
            return None
        model = PerformerCalendarOverrideModel(
            performer_id=performer.id,
            override_type=override_type,
            starts_at=starts_at,
            ends_at=ends_at,
            comment=comment,
        )
        self._session.add(model)
        await self._session.flush()
        timezone = await self.get_performer_timezone(performer.id)
        if timezone is None:
            return None
        return _override_to_dto(model, timezone)

    async def get_calendar_by_telegram_id(
        self,
        telegram_id: int,
    ) -> tuple[PerformerScheduleDTO | None, tuple[CalendarOverrideDTO, ...]] | None:
        performer = await self._get_performer_by_telegram_id(telegram_id)
        if performer is None:
            return None
        performer_timezone = await self.get_performer_timezone(performer.id)
        if performer_timezone is None:
            return None
        schedule = await self._get_active_schedule(performer.id)
        overrides_result = await self._session.execute(
            select(PerformerCalendarOverrideModel)
            .where(PerformerCalendarOverrideModel.performer_id == performer.id)
            .order_by(PerformerCalendarOverrideModel.starts_at),
        )
        overrides = tuple(
            _override_to_dto(model, performer_timezone)
            for model in overrides_result.scalars()
        )
        return _schedule_to_dto(schedule) if schedule is not None else None, overrides

    async def check(
        self,
        *,
        performer_id: UUID,
        service_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        exclude_order_id: UUID | None = None,
        exclude_match_id: UUID | None = None,
    ) -> AvailabilityCheckDTO:
        reasons: list[str] = []
        timezone = await self.get_performer_timezone(performer_id)
        if timezone is None:
            reasons.append("performer_not_found")
            return AvailabilityCheckDTO(performer_id, False, tuple(reasons))
        schedule_policy = await self._get_schedule_policy(service_id)
        if schedule_policy is None:
            reasons.append("service_not_found")
            return AvailabilityCheckDTO(performer_id, False, tuple(reasons))
        if await self._has_blocking_match(
            performer_id=performer_id,
            starts_at=starts_at,
            ends_at=ends_at,
            exclude_match_id=exclude_match_id,
        ):
            reasons.append("blocking_match")
        if await self._has_blocking_order(
            performer_id=performer_id,
            starts_at=starts_at,
            ends_at=ends_at,
            exclude_order_id=exclude_order_id,
        ):
            reasons.append("blocking_order")
        if await self._has_unavailable_override(performer_id, starts_at, ends_at):
            reasons.append("unavailable_override")
        if schedule_policy == "working_hours" and not await self._is_in_working_hours(
            performer_id,
            to_timezone(starts_at, timezone),
            to_timezone(ends_at, timezone),
        ):
            reasons.append("outside_working_hours")
        return AvailabilityCheckDTO(
            performer_id=performer_id,
            is_available=not reasons,
            reasons=tuple(reasons),
        )

    async def find_suitable_performers(
        self,
        *,
        city_id: UUID,
        service_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        objects_count: int,
        care_object_ids: tuple[UUID, ...],
        address_id: UUID | None,
        limit: int,
    ) -> tuple[SuitablePerformerDTO, ...]:
        statement = (
            select(PerformerModel, PerformerServiceModel, ServiceModel, AddressModel)
            .join(
                PerformerServiceModel,
                PerformerServiceModel.performer_id == PerformerModel.id,
            )
            .join(ServiceModel, ServiceModel.id == PerformerServiceModel.service_id)
            .outerjoin(
                AddressModel,
                AddressModel.id == PerformerModel.current_address_id,
            )
            .where(
                PerformerModel.city_id == city_id,
                PerformerModel.status == "active",
                PerformerModel.is_accepting_orders.is_(True),
                PerformerServiceModel.service_id == service_id,
                PerformerServiceModel.is_approved.is_(True),
                PerformerServiceModel.is_enabled.is_(True),
                PerformerServiceModel.performer_max_objects >= objects_count,
                ServiceModel.is_active.is_(True),
            )
            .order_by(PerformerModel.id)
        )
        result = await self._session.execute(statement)
        care_objects = await self._list_care_objects(care_object_ids)
        order_address = await self._get_address(address_id)
        suitable: list[SuitablePerformerDTO] = []
        for performer, performer_service, service, current_address in result.tuples():
            current_address_model = cast(AddressModel | None, current_address)
            if (
                service.location_policy == "performer_address"
                and current_address_model is None
            ):
                continue
            if not _constraints_match(performer_service.constraints, care_objects):
                continue
            availability = await self.check(
                performer_id=performer.id,
                service_id=service_id,
                starts_at=starts_at,
                ends_at=ends_at,
            )
            if not availability.is_available:
                continue
            suitable.append(
                SuitablePerformerDTO(
                    performer_id=performer.id,
                    full_name=performer.full_name,
                    service_id=service.id,
                    service_code=service.code,
                    service_name=service.name,
                    performer_max_objects=performer_service.performer_max_objects,
                    distance_km=_distance(order_address, current_address_model),
                    current_address_id=performer.current_address_id,
                ),
            )
        return tuple(_sort_suitable_performers(suitable)[:limit])

    async def _get_performer_by_telegram_id(
        self,
        telegram_id: int,
    ) -> PerformerModel | None:
        result = await self._session.execute(
            select(PerformerModel).where(PerformerModel.telegram_id == telegram_id),
        )
        return result.scalar_one_or_none()

    async def _get_schedule_policy(self, service_id: UUID) -> str | None:
        result = await self._session.execute(
            select(ServiceModel.schedule_policy).where(ServiceModel.id == service_id),
        )
        return result.scalar_one_or_none()

    async def _get_active_schedule(
        self,
        performer_id: UUID,
    ) -> PerformerScheduleModel | None:
        result = await self._session.execute(
            select(PerformerScheduleModel).where(
                PerformerScheduleModel.performer_id == performer_id,
                PerformerScheduleModel.is_active.is_(True),
            ),
        )
        return result.scalar_one_or_none()

    async def _has_blocking_match(
        self,
        *,
        performer_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        exclude_match_id: UUID | None,
    ) -> bool:
        statement = (
            select(func.count())
            .select_from(OrderMatchModel)
            .where(
                OrderMatchModel.performer_id == performer_id,
                OrderMatchModel.status.in_(("active", "selected")),
                OrderMatchModel.starts_at < ends_at,
                OrderMatchModel.ends_at > starts_at,
            )
        )
        if exclude_match_id is not None:
            statement = statement.where(OrderMatchModel.id != exclude_match_id)
        return await self._count(statement) > 0

    async def _has_blocking_order(
        self,
        *,
        performer_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        exclude_order_id: UUID | None,
    ) -> bool:
        statement = (
            select(func.count())
            .select_from(OrderModel)
            .where(
                OrderModel.selected_performer_id == performer_id,
                OrderModel.status == "confirmed",
                OrderModel.start_at < ends_at,
                OrderModel.end_at > starts_at,
            )
        )
        if exclude_order_id is not None:
            statement = statement.where(OrderModel.id != exclude_order_id)
        return await self._count(statement) > 0

    async def _has_unavailable_override(
        self,
        performer_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
    ) -> bool:
        return (
            await self._count(
                _overlap_override_statement(
                    performer_id=performer_id,
                    override_type="unavailable",
                    starts_at=starts_at,
                    ends_at=ends_at,
                ),
            )
            > 0
        )

    async def _is_in_working_hours(
        self,
        performer_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
    ) -> bool:
        if await self._count(
            select(func.count())
            .select_from(PerformerCalendarOverrideModel)
            .where(
                PerformerCalendarOverrideModel.performer_id == performer_id,
                PerformerCalendarOverrideModel.override_type == "available",
                PerformerCalendarOverrideModel.starts_at <= starts_at,
                PerformerCalendarOverrideModel.ends_at >= ends_at,
            ),
        ):
            return True
        if starts_at.date() != ends_at.date():
            return False
        schedule = await self._get_active_schedule(performer_id)
        if schedule is None:
            return False
        if starts_at.time() < schedule.work_start_time:
            return False
        if ends_at.time() > schedule.work_end_time:
            return False
        weekday = starts_at.isoweekday()
        if schedule.schedule_type == "every_day":
            return True
        if schedule.schedule_type == "weekdays":
            return weekday <= 5
        if schedule.schedule_type == "weekends":
            return weekday >= 6
        return schedule.work_days is not None and weekday in schedule.work_days

    async def _list_care_objects(
        self,
        care_object_ids: tuple[UUID, ...],
    ) -> tuple[CareObjectModel, ...]:
        if not care_object_ids:
            return ()
        result = await self._session.execute(
            select(CareObjectModel).where(
                CareObjectModel.id.in_(care_object_ids),
                CareObjectModel.deleted_at.is_(None),
            ),
        )
        return tuple(result.scalars())

    async def _get_address(self, address_id: UUID | None) -> AddressModel | None:
        if address_id is None:
            return None
        return await self._session.get(AddressModel, address_id)

    async def _count(self, statement: Select[tuple[int]]) -> int:
        result = await self._session.execute(statement)
        return int(result.scalar_one())


def _schedule_to_dto(model: PerformerScheduleModel) -> PerformerScheduleDTO:
    return PerformerScheduleDTO(
        id=model.id,
        performer_id=model.performer_id,
        schedule_type=model.schedule_type,
        work_days=tuple(model.work_days) if model.work_days is not None else None,
        work_start_time=model.work_start_time,
        work_end_time=model.work_end_time,
        is_active=model.is_active,
    )


def _override_to_dto(
    model: PerformerCalendarOverrideModel,
    timezone: str,
) -> CalendarOverrideDTO:
    return CalendarOverrideDTO(
        id=model.id,
        performer_id=model.performer_id,
        override_type=model.override_type,
        starts_at=model.starts_at,
        ends_at=model.ends_at,
        comment=model.comment,
        timezone=timezone,
    )


def _overlap_override_statement(
    *,
    performer_id: UUID,
    override_type: str,
    starts_at: datetime,
    ends_at: datetime,
) -> Select[tuple[int]]:
    return (
        select(func.count())
        .select_from(PerformerCalendarOverrideModel)
        .where(
            PerformerCalendarOverrideModel.performer_id == performer_id,
            PerformerCalendarOverrideModel.override_type == override_type,
            PerformerCalendarOverrideModel.starts_at < ends_at,
            PerformerCalendarOverrideModel.ends_at > starts_at,
        )
    )


def _constraints_match(
    constraints: dict[str, object],
    care_objects: tuple[CareObjectModel, ...],
) -> bool:
    age_groups = _string_set(constraints.get("accepted_age_groups"))
    if age_groups and any(obj.age_group not in age_groups for obj in care_objects):
        return False
    pet_sizes = _string_set(constraints.get("accepted_pet_sizes"))
    if pet_sizes and any(
        obj.object_type == "pet" and obj.pet_size not in pet_sizes
        for obj in care_objects
    ):
        return False
    return not (
        constraints.get("works_with_infants") is False
        and any(obj.age_group == "infant" for obj in care_objects)
    )


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _sort_suitable_performers(
    performers: list[SuitablePerformerDTO],
) -> list[SuitablePerformerDTO]:
    return sorted(
        performers,
        key=lambda item: (
            item.distance_km is None,
            item.distance_km if item.distance_km is not None else Decimal("0"),
            item.full_name.casefold(),
            str(item.performer_id),
        ),
    )


def _distance(
    order_address: AddressModel | None,
    current_address: AddressModel | None,
) -> Decimal | None:
    if order_address is None or current_address is None:
        return None
    if (
        order_address.latitude is None
        or order_address.longitude is None
        or current_address.latitude is None
        or current_address.longitude is None
    ):
        return None
    return haversine_distance_km(
        first_latitude=order_address.latitude,
        first_longitude=order_address.longitude,
        second_latitude=current_address.latitude,
        second_longitude=current_address.longitude,
    )

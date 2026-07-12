from datetime import datetime, time
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key
from backend.modules.availability.application import (
    AddCalendarOverrideCommand,
    AddCalendarOverrideUseCase,
    AvailabilityCheckDTO,
    CalendarOverrideDTO,
    CheckPerformerAvailabilityCommand,
    CheckPerformerAvailabilityUseCase,
    FindSuitablePerformersCommand,
    FindSuitablePerformersUseCase,
    GetPerformerCalendarUseCase,
    PerformerScheduleDTO,
    SetPerformerScheduleCommand,
    SetPerformerScheduleUseCase,
    SuitablePerformerDTO,
)
from backend.modules.availability.infrastructure import SqlAlchemyAvailabilityRepository

router = APIRouter(
    prefix="/api",
    tags=["availability"],
    dependencies=[Depends(require_service_key)],
)


class SetScheduleRequest(BaseModel):
    schedule_type: str
    work_days: list[int] | None = None
    work_start_time: time
    work_end_time: time


class AddOverrideRequest(BaseModel):
    override_type: str
    starts_at: datetime
    ends_at: datetime
    comment: str | None = Field(default=None, max_length=500)


class ScheduleResponse(BaseModel):
    id: str
    performer_id: str
    schedule_type: str
    work_days: list[int] | None
    work_start_time: str
    work_end_time: str
    is_active: bool


class CalendarOverrideResponse(BaseModel):
    id: str
    performer_id: str
    override_type: str
    starts_at: str
    ends_at: str
    comment: str | None


class CalendarResponse(BaseModel):
    schedule: ScheduleResponse | None
    overrides: list[CalendarOverrideResponse]


class AvailabilityCheckResponse(BaseModel):
    performer_id: str
    is_available: bool
    reasons: list[str]


class SuitablePerformerResponse(BaseModel):
    performer_id: str
    full_name: str
    service_id: str
    service_code: str
    service_name: str
    performer_max_objects: int
    distance_km: Decimal | None
    current_address_id: str | None


@router.patch("/performers/by-telegram/{telegram_id}/schedule")
async def set_schedule(
    telegram_id: int,
    request: SetScheduleRequest,
    container: Annotated[Container, Depends(get_container)],
) -> ScheduleResponse:
    async with container.session_factory() as session:
        schedule = await SetPerformerScheduleUseCase(
            SqlAlchemyAvailabilityRepository(session),
        ).execute(
            SetPerformerScheduleCommand(
                telegram_id=telegram_id,
                schedule_type=request.schedule_type,
                work_days=tuple(request.work_days)
                if request.work_days is not None
                else None,
                work_start_time=request.work_start_time,
                work_end_time=request.work_end_time,
            ),
        )
        await session.commit()
    return _schedule_response(schedule)


@router.post(
    "/performers/by-telegram/{telegram_id}/calendar-overrides",
    status_code=201,
)
async def add_override(
    telegram_id: int,
    request: AddOverrideRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CalendarOverrideResponse:
    async with container.session_factory() as session:
        override = await AddCalendarOverrideUseCase(
            SqlAlchemyAvailabilityRepository(session),
        ).execute(
            AddCalendarOverrideCommand(
                telegram_id=telegram_id,
                override_type=request.override_type,
                starts_at=request.starts_at,
                ends_at=request.ends_at,
                comment=request.comment,
            ),
        )
        await session.commit()
    return _override_response(override)


@router.get("/performers/by-telegram/{telegram_id}/calendar")
async def get_calendar(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> CalendarResponse:
    async with container.session_factory() as session:
        schedule, overrides = await GetPerformerCalendarUseCase(
            SqlAlchemyAvailabilityRepository(session),
        ).execute(telegram_id)
    return CalendarResponse(
        schedule=_schedule_response(schedule) if schedule is not None else None,
        overrides=[_override_response(override) for override in overrides],
    )


@router.get("/availability/performers/{performer_id}/check")
async def check_availability(
    performer_id: UUID,
    service_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    container: Annotated[Container, Depends(get_container)],
    exclude_order_id: UUID | None = None,
    exclude_match_id: UUID | None = None,
) -> AvailabilityCheckResponse:
    async with container.session_factory() as session:
        result = await CheckPerformerAvailabilityUseCase(
            SqlAlchemyAvailabilityRepository(session),
        ).execute(
            CheckPerformerAvailabilityCommand(
                performer_id=performer_id,
                service_id=service_id,
                starts_at=starts_at,
                ends_at=ends_at,
                exclude_order_id=exclude_order_id,
                exclude_match_id=exclude_match_id,
            ),
        )
    return _availability_response(result)


@router.get("/availability/suitable-performers")
async def find_suitable_performers(
    city_id: UUID,
    service_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    objects_count: int,
    container: Annotated[Container, Depends(get_container)],
    care_object_ids: Annotated[list[UUID] | None, Query()] = None,
    address_id: UUID | None = None,
    limit: int = 20,
) -> list[SuitablePerformerResponse]:
    async with container.session_factory() as session:
        performers = await FindSuitablePerformersUseCase(
            SqlAlchemyAvailabilityRepository(session),
        ).execute(
            FindSuitablePerformersCommand(
                city_id=city_id,
                service_id=service_id,
                starts_at=starts_at,
                ends_at=ends_at,
                objects_count=objects_count,
                care_object_ids=tuple(care_object_ids or ()),
                address_id=address_id,
                limit=limit,
            ),
        )
    return [_suitable_performer_response(performer) for performer in performers]


def _schedule_response(schedule: PerformerScheduleDTO) -> ScheduleResponse:
    return ScheduleResponse(
        id=str(schedule.id),
        performer_id=str(schedule.performer_id),
        schedule_type=schedule.schedule_type,
        work_days=list(schedule.work_days) if schedule.work_days is not None else None,
        work_start_time=schedule.work_start_time.isoformat(),
        work_end_time=schedule.work_end_time.isoformat(),
        is_active=schedule.is_active,
    )


def _override_response(override: CalendarOverrideDTO) -> CalendarOverrideResponse:
    return CalendarOverrideResponse(
        id=str(override.id),
        performer_id=str(override.performer_id),
        override_type=override.override_type,
        starts_at=override.starts_at.isoformat(),
        ends_at=override.ends_at.isoformat(),
        comment=override.comment,
    )


def _availability_response(result: AvailabilityCheckDTO) -> AvailabilityCheckResponse:
    return AvailabilityCheckResponse(
        performer_id=str(result.performer_id),
        is_available=result.is_available,
        reasons=list(result.reasons),
    )


def _suitable_performer_response(
    performer: SuitablePerformerDTO,
) -> SuitablePerformerResponse:
    return SuitablePerformerResponse(
        performer_id=str(performer.performer_id),
        full_name=performer.full_name,
        service_id=str(performer.service_id),
        service_code=performer.service_code,
        service_name=performer.service_name,
        performer_max_objects=performer.performer_max_objects,
        distance_km=performer.distance_km,
        current_address_id=str(performer.current_address_id)
        if performer.current_address_id is not None
        else None,
    )


__all__ = ["router"]

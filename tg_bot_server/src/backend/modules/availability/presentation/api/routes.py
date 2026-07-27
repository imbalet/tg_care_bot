from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key
from backend.modules.availability.application import (
    AddCalendarOverrideCommand,
    CheckPerformerAvailabilityCommand,
    FindSuitablePerformersCommand,
    SetPerformerScheduleCommand,
)

from .mappers import (
    availability_response,
    calendar_response,
    override_response,
    schedule_response,
    suitable_performer_response,
)
from .schemas import (
    AddOverrideRequest,
    AvailabilityCheckResponse,
    CalendarOverrideResponse,
    CalendarResponse,
    ScheduleResponse,
    SetScheduleRequest,
    SuitablePerformerResponse,
)

router = APIRouter(
    prefix="/api",
    tags=["availability"],
    dependencies=[Depends(require_service_key)],
)


@router.patch("/performers/by-telegram/{telegram_id}/schedule")
async def set_schedule(
    telegram_id: int,
    request: SetScheduleRequest,
    container: Annotated[Container, Depends(get_container)],
) -> ScheduleResponse:
    schedule = await container.availability.set_performer_schedule(
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
    return schedule_response(schedule)


@router.post(
    "/performers/by-telegram/{telegram_id}/calendar-overrides",
    status_code=201,
)
async def add_override(
    telegram_id: int,
    request: AddOverrideRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CalendarOverrideResponse:
    override = await container.availability.add_calendar_override(
        AddCalendarOverrideCommand(
            telegram_id=telegram_id,
            override_type=request.override_type,
            starts_at=request.starts_at,
            ends_at=request.ends_at,
            comment=request.comment,
        ),
    )
    return override_response(override)


@router.delete("/performers/by-telegram/{telegram_id}/calendar-overrides/{override_id}")
async def cancel_override(
    telegram_id: int,
    override_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> CalendarOverrideResponse:
    override = await container.availability.cancel_calendar_override(
        telegram_id=telegram_id,
        override_id=override_id,
    )
    return override_response(override)


@router.get("/performers/by-telegram/{telegram_id}/calendar")
async def get_calendar(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> CalendarResponse:
    (
        schedule,
        overrides,
        busy_intervals,
    ) = await container.availability.get_performer_calendar(
        telegram_id,
    )
    return calendar_response(schedule, overrides, busy_intervals)


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
    result = await container.availability.check_performer_availability(
        CheckPerformerAvailabilityCommand(
            performer_id=performer_id,
            service_id=service_id,
            starts_at=starts_at,
            ends_at=ends_at,
            exclude_order_id=exclude_order_id,
            exclude_match_id=exclude_match_id,
        ),
    )
    return availability_response(result)


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
    performers = await container.availability.find_suitable_performers(
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
    return [suitable_performer_response(performer) for performer in performers]

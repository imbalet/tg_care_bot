from backend.modules.availability.application import (
    AvailabilityCheckDTO,
    CalendarOverrideDTO,
    PerformerScheduleDTO,
    SuitablePerformerDTO,
)

from .schemas import (
    AvailabilityCheckResponse,
    CalendarOverrideResponse,
    CalendarResponse,
    ScheduleResponse,
    SuitablePerformerResponse,
)


def schedule_response(schedule: PerformerScheduleDTO) -> ScheduleResponse:
    return ScheduleResponse(
        id=str(schedule.id),
        performer_id=str(schedule.performer_id),
        schedule_type=schedule.schedule_type,
        work_days=list(schedule.work_days) if schedule.work_days is not None else None,
        work_start_time=schedule.work_start_time.isoformat(),
        work_end_time=schedule.work_end_time.isoformat(),
        is_active=schedule.is_active,
    )


def override_response(override: CalendarOverrideDTO) -> CalendarOverrideResponse:
    return CalendarOverrideResponse(
        id=str(override.id),
        performer_id=str(override.performer_id),
        override_type=override.override_type,
        starts_at=override.starts_at.isoformat(),
        ends_at=override.ends_at.isoformat(),
        comment=override.comment,
    )


def calendar_response(
    schedule: PerformerScheduleDTO | None,
    overrides: tuple[CalendarOverrideDTO, ...],
) -> CalendarResponse:
    return CalendarResponse(
        schedule=schedule_response(schedule) if schedule is not None else None,
        overrides=[override_response(override) for override in overrides],
    )


def availability_response(result: AvailabilityCheckDTO) -> AvailabilityCheckResponse:
    return AvailabilityCheckResponse(
        performer_id=str(result.performer_id),
        is_available=result.is_available,
        reasons=list(result.reasons),
    )


def suitable_performer_response(
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

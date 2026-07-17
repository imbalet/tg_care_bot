from dataclasses import dataclass
from datetime import datetime, time
from uuid import UUID

from backend.common.domain import NotFoundError, ValidationError
from backend.modules.availability.application.dto import (
    AvailabilityCheckDTO,
    CalendarOverrideDTO,
    PerformerScheduleDTO,
    SuitablePerformerDTO,
)
from backend.modules.availability.application.interfaces import (
    AvailabilityRepository,
    ConflictChecker,
)

SCHEDULE_TYPES = {"every_day", "weekdays", "weekends", "custom"}
OVERRIDE_TYPES = {"available", "unavailable"}


@dataclass(frozen=True)
class SetPerformerScheduleCommand:
    telegram_id: int
    schedule_type: str
    work_days: tuple[int, ...] | None
    work_start_time: time
    work_end_time: time


class SetPerformerScheduleUseCase:
    def __init__(self, repository: AvailabilityRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        command: SetPerformerScheduleCommand,
    ) -> PerformerScheduleDTO:
        if command.schedule_type not in SCHEDULE_TYPES:
            raise ValidationError("Schedule type is invalid")
        if command.work_start_time >= command.work_end_time:
            raise ValidationError("Schedule start must be before end")
        if command.schedule_type == "custom":
            if not command.work_days:
                raise ValidationError("Custom schedule requires work days")
            if any(day < 1 or day > 7 for day in command.work_days):
                raise ValidationError("Work days must be between 1 and 7")
        elif command.work_days is not None:
            raise ValidationError("Work days are allowed only for custom schedule")
        schedule = await self._repository.set_schedule(
            telegram_id=command.telegram_id,
            schedule_type=command.schedule_type,
            work_days=command.work_days,
            work_start_time=command.work_start_time,
            work_end_time=command.work_end_time,
        )
        if schedule is None:
            raise NotFoundError("Performer not found")
        return schedule


@dataclass(frozen=True)
class AddCalendarOverrideCommand:
    telegram_id: int
    override_type: str
    starts_at: datetime
    ends_at: datetime
    comment: str | None


class AddCalendarOverrideUseCase:
    def __init__(self, repository: AvailabilityRepository) -> None:
        self._repository = repository

    async def execute(self, command: AddCalendarOverrideCommand) -> CalendarOverrideDTO:
        if command.override_type not in OVERRIDE_TYPES:
            raise ValidationError("Calendar override type is invalid")
        if command.starts_at >= command.ends_at:
            raise ValidationError("Override start must be before end")
        override = await self._repository.add_override(
            telegram_id=command.telegram_id,
            override_type=command.override_type,
            starts_at=command.starts_at,
            ends_at=command.ends_at,
            comment=command.comment,
        )
        if override is None:
            raise NotFoundError("Performer not found")
        return override


class GetPerformerCalendarUseCase:
    def __init__(self, repository: AvailabilityRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        telegram_id: int,
    ) -> tuple[PerformerScheduleDTO | None, tuple[CalendarOverrideDTO, ...]]:
        calendar = await self._repository.get_calendar_by_telegram_id(telegram_id)
        if calendar is None:
            raise NotFoundError("Performer not found")
        return calendar


@dataclass(frozen=True)
class CheckPerformerAvailabilityCommand:
    performer_id: UUID
    service_id: UUID
    starts_at: datetime
    ends_at: datetime
    exclude_order_id: UUID | None = None
    exclude_match_id: UUID | None = None


class CheckPerformerAvailabilityUseCase:
    def __init__(self, conflict_checker: ConflictChecker) -> None:
        self._conflict_checker = conflict_checker

    async def execute(
        self,
        command: CheckPerformerAvailabilityCommand,
    ) -> AvailabilityCheckDTO:
        if command.starts_at >= command.ends_at:
            raise ValidationError("Availability interval is invalid")
        return await self._conflict_checker.check(
            performer_id=command.performer_id,
            service_id=command.service_id,
            starts_at=command.starts_at,
            ends_at=command.ends_at,
            exclude_order_id=command.exclude_order_id,
            exclude_match_id=command.exclude_match_id,
        )


@dataclass(frozen=True)
class FindSuitablePerformersCommand:
    city_id: UUID
    service_id: UUID
    starts_at: datetime
    ends_at: datetime
    objects_count: int
    care_object_ids: tuple[UUID, ...]
    address_id: UUID | None
    limit: int = 20


class FindSuitablePerformersUseCase:
    def __init__(self, repository: AvailabilityRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        command: FindSuitablePerformersCommand,
    ) -> tuple[SuitablePerformerDTO, ...]:
        if command.starts_at >= command.ends_at:
            raise ValidationError("Availability interval is invalid")
        if command.objects_count < 1:
            raise ValidationError("Objects count must be positive")
        if command.limit < 1 or command.limit > 100:
            raise ValidationError("Limit must be between 1 and 100")
        return await self._repository.find_suitable_performers(
            city_id=command.city_id,
            service_id=command.service_id,
            starts_at=command.starts_at,
            ends_at=command.ends_at,
            objects_count=command.objects_count,
            care_object_ids=command.care_object_ids,
            address_id=command.address_id,
            limit=command.limit,
        )

from datetime import datetime, time
from typing import Protocol
from uuid import UUID

from backend.modules.availability.application.dto import (
    AvailabilityCheckDTO,
    CalendarOverrideDTO,
    PerformerScheduleDTO,
    SuitablePerformerDTO,
)


class ConflictChecker(Protocol):
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
        pass


class AvailabilityRepository(ConflictChecker, Protocol):
    async def set_schedule(
        self,
        *,
        telegram_id: int,
        schedule_type: str,
        work_days: tuple[int, ...] | None,
        work_start_time: time,
        work_end_time: time,
    ) -> PerformerScheduleDTO | None:
        pass

    async def add_override(
        self,
        *,
        telegram_id: int,
        override_type: str,
        starts_at: datetime,
        ends_at: datetime,
        comment: str | None,
    ) -> CalendarOverrideDTO | None:
        pass

    async def get_calendar_by_telegram_id(
        self,
        telegram_id: int,
    ) -> tuple[PerformerScheduleDTO | None, tuple[CalendarOverrideDTO, ...]] | None:
        pass

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
        pass


__all__ = ["AvailabilityRepository", "ConflictChecker"]

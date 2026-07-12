from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4

import pytest

from backend.common.domain import ValidationError
from backend.modules.availability.application import (
    AddCalendarOverrideCommand,
    AddCalendarOverrideUseCase,
    AvailabilityCheckDTO,
    CalendarOverrideDTO,
    CheckPerformerAvailabilityCommand,
    CheckPerformerAvailabilityUseCase,
    FindSuitablePerformersCommand,
    FindSuitablePerformersUseCase,
    PerformerScheduleDTO,
    SetPerformerScheduleCommand,
    SetPerformerScheduleUseCase,
    SuitablePerformerDTO,
)


class FakeAvailabilityRepository:
    def __init__(self) -> None:
        self.performer_id = uuid4()
        self.telegram_id = 123
        self.schedule: PerformerScheduleDTO | None = None
        self.overrides: list[CalendarOverrideDTO] = []

    async def set_schedule(
        self,
        *,
        telegram_id: int,
        schedule_type: str,
        work_days: tuple[int, ...] | None,
        work_start_time: time,
        work_end_time: time,
    ) -> PerformerScheduleDTO | None:
        if telegram_id != self.telegram_id:
            return None
        self.schedule = PerformerScheduleDTO(
            id=uuid4(),
            performer_id=self.performer_id,
            schedule_type=schedule_type,
            work_days=work_days,
            work_start_time=work_start_time,
            work_end_time=work_end_time,
            is_active=True,
        )
        return self.schedule

    async def add_override(
        self,
        *,
        telegram_id: int,
        override_type: str,
        starts_at: datetime,
        ends_at: datetime,
        comment: str | None,
    ) -> CalendarOverrideDTO | None:
        if telegram_id != self.telegram_id:
            return None
        override = CalendarOverrideDTO(
            id=uuid4(),
            performer_id=self.performer_id,
            override_type=override_type,
            starts_at=starts_at,
            ends_at=ends_at,
            comment=comment,
        )
        self.overrides.append(override)
        return override

    async def get_calendar_by_telegram_id(
        self,
        telegram_id: int,
    ) -> tuple[PerformerScheduleDTO | None, tuple[CalendarOverrideDTO, ...]] | None:
        if telegram_id != self.telegram_id:
            return None
        return self.schedule, tuple(self.overrides)

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
        return AvailabilityCheckDTO(
            performer_id=performer_id,
            is_available=True,
            reasons=(),
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
        return ()


@pytest.mark.asyncio
async def test_sets_custom_schedule() -> None:
    repository = FakeAvailabilityRepository()

    schedule = await SetPerformerScheduleUseCase(repository).execute(
        SetPerformerScheduleCommand(
            telegram_id=repository.telegram_id,
            schedule_type="custom",
            work_days=(1, 3, 5),
            work_start_time=time(9),
            work_end_time=time(18),
        ),
    )

    assert schedule.work_days == (1, 3, 5)


@pytest.mark.asyncio
async def test_rejects_invalid_schedule_shape() -> None:
    repository = FakeAvailabilityRepository()

    with pytest.raises(ValidationError):
        await SetPerformerScheduleUseCase(repository).execute(
            SetPerformerScheduleCommand(
                telegram_id=repository.telegram_id,
                schedule_type="weekdays",
                work_days=(1, 2),
                work_start_time=time(9),
                work_end_time=time(18),
            ),
        )


@pytest.mark.asyncio
async def test_rejects_invalid_override_interval() -> None:
    repository = FakeAvailabilityRepository()
    now = datetime.now(UTC)

    with pytest.raises(ValidationError):
        await AddCalendarOverrideUseCase(repository).execute(
            AddCalendarOverrideCommand(
                telegram_id=repository.telegram_id,
                override_type="unavailable",
                starts_at=now,
                ends_at=now,
                comment=None,
            ),
        )


@pytest.mark.asyncio
async def test_check_availability_rejects_empty_interval() -> None:
    repository = FakeAvailabilityRepository()
    now = datetime.now(UTC)

    with pytest.raises(ValidationError):
        await CheckPerformerAvailabilityUseCase(repository).execute(
            CheckPerformerAvailabilityCommand(
                performer_id=repository.performer_id,
                service_id=uuid4(),
                starts_at=now,
                ends_at=now,
            ),
        )


@pytest.mark.asyncio
async def test_find_suitable_performers_validates_limit() -> None:
    repository = FakeAvailabilityRepository()
    now = datetime.now(UTC)

    with pytest.raises(ValidationError):
        await FindSuitablePerformersUseCase(repository).execute(
            FindSuitablePerformersCommand(
                city_id=uuid4(),
                service_id=uuid4(),
                starts_at=now,
                ends_at=now + timedelta(hours=1),
                objects_count=1,
                care_object_ids=(),
                address_id=None,
                limit=101,
            ),
        )

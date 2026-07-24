from datetime import UTC, datetime, time, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.common.domain import ValidationError
from backend.modules.availability.application.use_cases import (
    CheckPerformerAvailabilityCommand,
    CheckPerformerAvailabilityUseCase,
    FindSuitablePerformersCommand,
    FindSuitablePerformersUseCase,
    SetPerformerScheduleCommand,
    SetPerformerScheduleUseCase,
)


@pytest.mark.unit
async def test_custom_schedule_requires_valid_work_days() -> None:
    repository = AsyncMock()
    use_case = SetPerformerScheduleUseCase(repository)

    with pytest.raises(ValidationError, match="Work days"):
        await use_case.execute(
            SetPerformerScheduleCommand(
                telegram_id=100,
                schedule_type="custom",
                work_days=(0,),
                work_start_time=time(9),
                work_end_time=time(18),
            ),
        )

    repository.set_schedule.assert_not_awaited()


@pytest.mark.unit
async def test_availability_rejects_reversed_interval_before_repository_call() -> None:
    checker = AsyncMock()
    now = datetime(2026, 1, 1, 10, tzinfo=UTC)

    with pytest.raises(ValidationError, match="interval"):
        await CheckPerformerAvailabilityUseCase(checker).execute(
            CheckPerformerAvailabilityCommand(
                performer_id=uuid4(),
                service_id=uuid4(),
                starts_at=now + timedelta(hours=1),
                ends_at=now,
            ),
        )

    checker.check.assert_not_awaited()


@pytest.mark.unit
async def test_suitable_performers_rejects_invalid_count_and_limit() -> None:
    repository = AsyncMock()
    use_case = FindSuitablePerformersUseCase(repository)
    now = datetime(2026, 1, 1, 10, tzinfo=UTC)

    with pytest.raises(ValidationError, match="positive"):
        await use_case.execute(
            FindSuitablePerformersCommand(
                city_id=uuid4(),
                service_id=uuid4(),
                starts_at=now,
                ends_at=now + timedelta(hours=1),
                objects_count=0,
                care_object_ids=(),
                address_id=None,
            ),
        )

    with pytest.raises(ValidationError, match="between 1 and 100"):
        await use_case.execute(
            FindSuitablePerformersCommand(
                city_id=uuid4(),
                service_id=uuid4(),
                starts_at=now,
                ends_at=now + timedelta(hours=1),
                objects_count=1,
                care_object_ids=(uuid4(),),
                address_id=None,
                limit=101,
            ),
        )

    repository.find_suitable_performers.assert_not_awaited()

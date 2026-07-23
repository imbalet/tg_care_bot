from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from backend.modules.system_checks.application.use_cases import (
    CreateSystemCheckCommand,
    CreateSystemCheckUseCase,
)
from tests.support.fakes import FakeClock


@pytest.mark.unit
async def test_system_check_use_case_adds_record_and_commits_uow() -> None:
    session = SimpleNamespace(add=Mock())
    uow = AsyncMock()
    uow.__aenter__.return_value = SimpleNamespace(session=session, commit=AsyncMock())
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))

    result = await CreateSystemCheckUseCase(uow, clock).execute(
        CreateSystemCheckCommand(name="database"),
    )

    assert result.name == "database"
    uow.__aenter__.return_value.commit.assert_awaited_once()
    session.add.assert_called_once()

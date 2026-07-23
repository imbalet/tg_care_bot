from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.common.domain import ValidationError
from backend.modules.orders.application.use_cases import (
    SubmitOrderReportCommand,
    SubmitOrderReportUseCase,
)
from tests.support.fakes import FakeObjectStorage


@pytest.mark.unit
@pytest.mark.parametrize(
    ("problem_flag", "problem_description"),
    [(True, None), (False, "unexpected")],
)
async def test_report_requires_consistent_problem_fields(
    problem_flag: bool,
    problem_description: str | None,
) -> None:
    use_case = SubmitOrderReportUseCase(
        AsyncMock(),
        AsyncMock(),
        FakeObjectStorage(),
    )

    with pytest.raises(ValidationError):
        await use_case.execute(
            SubmitOrderReportCommand(
                order_id=uuid4(),
                performer_id=uuid4(),
                completed_work="Completed",
                comment=None,
                problem_flag=problem_flag,
                problem_description=problem_description,
                file_ids=(),
            ),
        )


@pytest.mark.unit
async def test_report_rejects_blank_completed_work() -> None:
    use_case = SubmitOrderReportUseCase(
        AsyncMock(),
        AsyncMock(),
        FakeObjectStorage(),
    )

    with pytest.raises(ValidationError, match="Completed work"):
        await use_case.execute(
            SubmitOrderReportCommand(
                order_id=uuid4(),
                performer_id=uuid4(),
                completed_work="   ",
                comment=None,
                problem_flag=False,
                problem_description=None,
                file_ids=(),
            ),
        )

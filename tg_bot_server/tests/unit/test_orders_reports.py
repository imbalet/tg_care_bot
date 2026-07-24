from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from backend.common.domain import ValidationError
from backend.modules.files.application.dto import FileDTO
from backend.modules.orders.application.dto import OrderReportDTO
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


@pytest.mark.unit
async def test_report_without_photo_is_allowed_with_customer_consent() -> None:
    order_id = uuid4()
    performer_id = uuid4()
    report = OrderReportDTO(
        id=uuid4(),
        order_id=order_id,
        performer_id=performer_id,
        completed_work="Care completed",
        comment=None,
        problem_flag=False,
        problem_description=None,
        submitted_at=datetime.now(UTC),
        file_ids=(),
    )
    order_repository = AsyncMock()
    order_repository.get_order.return_value = SimpleNamespace(
        photo_policy="requires_customer_consent",
        report_photo_consent=True,
    )
    order_repository.submit_report.return_value = report
    pricing_repository = AsyncMock()
    pricing_repository.get_integer_setting.return_value = 24 * 60

    result = await SubmitOrderReportUseCase(
        order_repository,
        AsyncMock(),
        FakeObjectStorage(),
        pricing_repository,
    ).execute(
        SubmitOrderReportCommand(
            order_id=order_id,
            performer_id=performer_id,
            completed_work="Care completed",
            comment=None,
            problem_flag=False,
            problem_description=None,
            file_ids=(),
        ),
    )

    assert result == report
    order_repository.submit_report.assert_awaited_once()


@pytest.mark.unit
async def test_report_without_photo_is_allowed_without_customer_consent() -> None:
    order_id = uuid4()
    performer_id = uuid4()
    report = OrderReportDTO(
        id=uuid4(),
        order_id=order_id,
        performer_id=performer_id,
        completed_work="Care completed",
        comment=None,
        problem_flag=False,
        problem_description=None,
        submitted_at=datetime.now(UTC),
        file_ids=(),
    )
    order_repository = AsyncMock()
    order_repository.get_order.return_value = SimpleNamespace(
        photo_policy="requires_customer_consent",
        report_photo_consent=False,
    )
    order_repository.submit_report.return_value = report

    result = await SubmitOrderReportUseCase(
        order_repository,
        AsyncMock(),
        FakeObjectStorage(),
    ).execute(
        SubmitOrderReportCommand(
            order_id=order_id,
            performer_id=performer_id,
            completed_work="Care completed",
            comment=None,
            problem_flag=False,
            problem_description=None,
            file_ids=(),
        ),
    )

    assert result == report
    order_repository.submit_report.assert_awaited_once()


def _report_file(file_id: UUID, storage_key: str) -> FileDTO:
    return FileDTO(
        id=file_id,
        telegram_file_id=None,
        bucket="test-bucket",
        storage_key=storage_key,
        original_name="report.png",
        mime_type="image/png",
        size_bytes=16,
        checksum="checksum",
        status="uploaded",
        created_at=datetime.now(UTC),
        deleted_at=None,
    )


@pytest.mark.unit
async def test_report_photo_is_allowed_with_customer_consent() -> None:
    order_id = uuid4()
    performer_id = uuid4()
    file_id = uuid4()
    report = OrderReportDTO(
        id=uuid4(),
        order_id=order_id,
        performer_id=performer_id,
        completed_work="Care completed",
        comment=None,
        problem_flag=False,
        problem_description=None,
        submitted_at=datetime.now(UTC),
        file_ids=(file_id,),
    )
    order_repository = AsyncMock()
    order_repository.get_order.return_value = SimpleNamespace(
        photo_policy="requires_customer_consent",
        report_photo_consent=True,
    )
    order_repository.submit_report.return_value = report
    file_repository = AsyncMock()
    file_repository.get.return_value = _report_file(file_id, "reports/report.png")
    storage = FakeObjectStorage()
    storage.objects["reports/report.png"] = (
        b"\x89PNG\r\n\x1a\ncontent",
        "image/png",
    )

    result = await SubmitOrderReportUseCase(
        order_repository,
        file_repository,
        storage,
    ).execute(
        SubmitOrderReportCommand(
            order_id=order_id,
            performer_id=performer_id,
            completed_work="Care completed",
            comment=None,
            problem_flag=False,
            problem_description=None,
            file_ids=(file_id,),
        ),
    )

    assert result == report
    order_repository.submit_report.assert_awaited_once()
    file_repository.add_link.assert_awaited_once()


@pytest.mark.unit
async def test_report_photo_is_rejected_without_customer_consent() -> None:
    order_id = uuid4()
    performer_id = uuid4()
    file_id = uuid4()
    order_repository = AsyncMock()
    order_repository.get_order.return_value = SimpleNamespace(
        photo_policy="requires_customer_consent",
        report_photo_consent=False,
    )
    file_repository = AsyncMock()
    file_repository.get.return_value = _report_file(file_id, "reports/report.png")
    storage = FakeObjectStorage()
    storage.objects["reports/report.png"] = (
        b"\x89PNG\r\n\x1a\ncontent",
        "image/png",
    )

    with pytest.raises(ValidationError, match="consent"):
        await SubmitOrderReportUseCase(
            order_repository,
            file_repository,
            storage,
        ).execute(
            SubmitOrderReportCommand(
                order_id=order_id,
                performer_id=performer_id,
                completed_work="Care completed",
                comment=None,
                problem_flag=False,
                problem_description=None,
                file_ids=(file_id,),
            ),
        )

    order_repository.submit_report.assert_not_awaited()
    file_repository.add_link.assert_not_awaited()

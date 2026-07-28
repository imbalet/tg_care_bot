from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from backend.common.domain import ValidationError
from backend.modules.performers.application.dto import PerformerDTO
from backend.modules.performers.application.use_cases import (
    SetPerformerAcceptingOrdersCommand,
    SetPerformerAcceptingOrdersUseCase,
)


def _performer(*, current_address_id: UUID | None) -> PerformerDTO:
    return PerformerDTO(
        id=uuid4(),
        telegram_id=123,
        full_name="Исполнитель",
        phone="+79990000000",
        telegram_username=None,
        contact_method="phone",
        city_id=uuid4(),
        about_text=None,
        status="active",
        is_accepting_orders=False,
        current_address_id=current_address_id,
    )


def _service() -> object:
    return type(
        "Service",
        (),
        {"is_approved": True, "is_enabled": True},
    )()


@pytest.mark.unit
async def test_accepting_orders_requires_current_work_address() -> None:
    repository = AsyncMock()
    repository.get_performer_by_telegram_id.return_value = _performer(
        current_address_id=None,
    )

    with pytest.raises(ValidationError, match="performer address"):
        await SetPerformerAcceptingOrdersUseCase(repository).execute(
            SetPerformerAcceptingOrdersCommand(
                telegram_id=123,
                is_accepting_orders=True,
            ),
        )

    repository.list_services_by_telegram_id.assert_not_awaited()
    repository.set_accepting_orders_by_telegram_id.assert_not_awaited()


@pytest.mark.unit
async def test_accepting_orders_with_address_still_requires_enabled_service() -> None:
    repository = AsyncMock()
    repository.get_performer_by_telegram_id.return_value = _performer(
        current_address_id=uuid4(),
    )
    repository.list_services_by_telegram_id.return_value = ()

    with pytest.raises(ValidationError, match="approved service"):
        await SetPerformerAcceptingOrdersUseCase(repository).execute(
            SetPerformerAcceptingOrdersCommand(
                telegram_id=123,
                is_accepting_orders=True,
            ),
        )


@pytest.mark.unit
async def test_accepting_orders_with_address_and_enabled_service_is_allowed() -> None:
    repository = AsyncMock()
    performer = _performer(current_address_id=uuid4())
    repository.get_performer_by_telegram_id.return_value = performer
    repository.list_services_by_telegram_id.return_value = (_service(),)
    repository.set_accepting_orders_by_telegram_id.return_value = performer

    result = await SetPerformerAcceptingOrdersUseCase(repository).execute(
        SetPerformerAcceptingOrdersCommand(telegram_id=123, is_accepting_orders=True),
    )

    assert result == performer
    repository.set_accepting_orders_by_telegram_id.assert_awaited_once_with(
        telegram_id=123,
        is_accepting_orders=True,
    )


@pytest.mark.unit
async def test_disabling_accepting_orders_does_not_require_address() -> None:
    repository = AsyncMock()
    performer = _performer(current_address_id=None)
    repository.set_accepting_orders_by_telegram_id.return_value = performer

    result = await SetPerformerAcceptingOrdersUseCase(repository).execute(
        SetPerformerAcceptingOrdersCommand(telegram_id=123, is_accepting_orders=False),
    )

    assert result == performer
    repository.set_accepting_orders_by_telegram_id.assert_awaited_once_with(
        telegram_id=123,
        is_accepting_orders=False,
    )

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from executor_bot.application.dto import AddressDTO, CalendarDTO
from executor_bot.presentation.callbacks import (
    CalendarCancelUnavailableCallback,
    ExecutorOrderCardCallback,
)
from executor_bot.presentation.handlers.addresses.router import _advance_or_create
from executor_bot.presentation.handlers.services_calendar import (
    cancel_unavailable_period,
)
from executor_bot.presentation.ui import order_location_keyboard
from executor_bot.presentation.ui.screens.keyboards import (
    work_address_created_keyboard,
)


def test_order_location_keyboard_returns_to_order() -> None:
    order_id = str(uuid4())

    markup = order_location_keyboard(order_id=order_id, group="active", page=2)

    callback = markup.inline_keyboard[0][0].callback_data
    assert callback is not None
    data = ExecutorOrderCardCallback.unpack(callback)
    assert data.order_id == order_id
    assert data.page == 2


def test_created_work_address_keyboard_has_navigation() -> None:
    markup = work_address_created_keyboard()
    labels = [button.text for row in markup.inline_keyboard for button in row]

    assert "К рабочим адресам" in labels
    assert "Главное меню" in labels


@pytest.mark.asyncio
async def test_created_work_address_message_has_navigation() -> None:
    backend = AsyncMock()
    backend.create_work_address.return_value = AddressDTO(
        id=uuid4(),
        city_id=uuid4(),
        address_text="Ростов-на-Дону, ул. Тестовая, 1",
        entrance=None,
        floor=None,
        apartment=None,
        comment=None,
    )
    state = AsyncMock()
    responder = AsyncMock()
    context = type("Context", (), {"telegram_id": 123})()

    await _advance_or_create(
        event=object(),
        bot=object(),
        state=state,
        backend_client=backend,
        telegram_responder=responder,
        telegram_user_context=context,
        draft={
            "city_id": str(uuid4()),
            "unrestricted_value": "ул. Тестовая, 1",
            "extra_index": 3,
        },
    )

    markup = responder.update.await_args.kwargs["reply_markup"]
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert "К рабочим адресам" in labels
    assert "Главное меню" in labels


@pytest.mark.asyncio
async def test_cancel_unavailability_refreshes_calendar_with_keyboard() -> None:
    backend = AsyncMock()
    backend.get_calendar.return_value = CalendarDTO(
        schedule=None,
        overrides=(),
        busy_intervals=(),
    )
    responder = AsyncMock()
    context = type("Context", (), {"telegram_id": 123})()

    await cancel_unavailable_period(
        callback=object(),
        bot=object(),
        backend_client=backend,
        telegram_responder=responder,
        telegram_user_context=context,
        callback_data=CalendarCancelUnavailableCallback(override_id=str(uuid4())),
    )

    assert "Календарь исполнителя" in responder.update.await_args.kwargs["text"]
    assert responder.update.await_args.kwargs["reply_markup"] is not None

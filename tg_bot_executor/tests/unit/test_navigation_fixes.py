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
    _parse_time,
    cancel_unavailable_period,
)
from executor_bot.presentation.navigation import list_categories
from executor_bot.presentation.ui import order_location_keyboard
from executor_bot.presentation.ui.screens.keyboards import (
    fallback_keyboard,
    responses_keyboard,
    work_address_created_keyboard,
    work_address_suggestions_keyboard,
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


def test_work_address_suggestions_keyboard_allows_retry() -> None:
    markup = work_address_suggestions_keyboard((object(),))
    labels = [button.text for row in markup.inline_keyboard for button in row]

    assert "Ввести заново" in labels


def test_help_fallback_does_not_repeat_help_or_support() -> None:
    markup = fallback_keyboard(
        include_main_menu=True,
        include_help=False,
        include_support=False,
        support_label="Аккаунт поддержки",
        support_url="https://t.me/support",
    )
    labels = [button.text for row in markup.inline_keyboard for button in row]

    assert labels == ["Главное меню", "Аккаунт поддержки"]
    assert markup.inline_keyboard[1][0].url == "https://t.me/support"


def test_work_address_views_mark_current_address() -> None:
    from executor_bot.presentation.ui import (
        work_address_card_text,
        work_addresses_list_text,
    )

    item = {"address_text": "ул. Тестовая, 1", "is_current": True}

    assert "текущий" in work_addresses_list_text((item,))
    assert "Текущий рабочий адрес" in work_address_card_text(item)


def test_responses_keyboard_has_direct_section() -> None:
    keyboard = responses_keyboard((), "direct")
    labels = [button.text for row in keyboard.inline_keyboard for button in row]

    assert labels == ["Активные", "Выбранные", "Закрытые", "Direct", "Главное меню"]


def test_unavailable_period_time_parser_accepts_clock_values() -> None:
    assert _parse_time("09:30") is not None
    assert _parse_time("25:00") is None


@pytest.mark.asyncio
async def test_executor_categories_include_only_approved_service_categories() -> None:
    backend = AsyncMock()
    service = type("Service", (), {"code": "care", "name": "Уход"})()
    hidden_service = type("Service", (), {"code": "walk", "name": "Прогулка"})()
    backend.list_catalog_categories.return_value = (
        type("Category", (), {"code": "care_category", "services": (service,)})(),
        type(
            "Category",
            (),
            {"code": "walk_category", "services": (hidden_service,)},
        )(),
    )
    backend.list_performer_services.return_value = (
        type("PerformerService", (), {"service_code": "care", "is_approved": True})(),
        type("PerformerService", (), {"service_code": "walk", "is_approved": False})(),
    )

    categories = await list_categories(backend, telegram_id=123)

    assert [category.code for category in categories] == ["care_category"]


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

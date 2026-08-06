from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from executor_bot.application.dto import AddressDTO, CalendarDTO, OrderMatchDTO
from executor_bot.application.errors import BackendValidationError
from executor_bot.presentation.callbacks import (
    CalendarCancelUnavailableCallback,
    ExecutorOrderCardCallback,
    ExecutorResponseCardCallback,
    ExecutorResponsesCallback,
    WorkAddressDeleteCallback,
)
from executor_bot.presentation.contexts import TelegramUserContext
from executor_bot.presentation.handlers.addresses.router import (
    _advance_or_create,
    delete_address,
)
from executor_bot.presentation.handlers.avatar import _upload
from executor_bot.presentation.handlers.orders.router import (
    executor_response_card_callback,
)
from executor_bot.presentation.handlers.services_calendar import (
    _parse_time,
    cancel_unavailable_period,
    save_unavailable_end_time,
)
from executor_bot.presentation.navigation import list_categories, show_category_select
from executor_bot.presentation.ui import order_location_keyboard
from executor_bot.presentation.ui.screens.keyboards import (
    direct_response_card_keyboard,
    fallback_keyboard,
    response_card_keyboard,
    responses_keyboard,
    work_address_created_keyboard,
    work_address_suggestions_keyboard,
)
from executor_bot.presentation.ui.screens.texts import response_card_text


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
        include_support=True,
        support_label="Аккаунт поддержки",
        support_url="https://t.me/support",
    )
    labels = [button.text for row in markup.inline_keyboard for button in row]

    assert labels == ["Главное меню", "Аккаунт поддержки"]
    assert "Связаться с поддержкой" not in labels
    assert markup.inline_keyboard[1][0].url == "https://t.me/support"


def test_work_address_views_mark_current_address() -> None:
    from executor_bot.presentation.ui import (
        work_address_card_text,
        work_addresses_list_text,
    )

    item = {"address_text": "ул. Тестовая, 1", "is_current": True}

    assert "текущий" in work_addresses_list_text((item,))
    assert "Текущий рабочий адрес" in work_address_card_text(item)


def test_responses_keyboard_hides_direct_section() -> None:
    keyboard = responses_keyboard((), "direct")
    labels = [button.text for row in keyboard.inline_keyboard for button in row]

    assert labels == ["Активные", "Выбранные", "Закрытые", "Главное меню"]


def test_response_button_points_to_match_card() -> None:
    match_id = uuid4()
    order_id = uuid4()
    match = OrderMatchDTO(
        id=match_id,
        order_id=order_id,
        performer_id=uuid4(),
        source="pool",
        status="active",
        starts_at=datetime(2026, 7, 31, 10, tzinfo=UTC),
        ends_at=datetime(2026, 7, 31, 12, tzinfo=UTC),
        response_expires_at=datetime(2026, 7, 31, 7, tzinfo=UTC),
        selected_at=None,
        closed_at=None,
        close_reason=None,
        timezone="Europe/Moscow",
        service_name="Прогулка",
        total_amount=Decimal("1200.00"),
        distance_km=Decimal("3.5"),
        customer_comment="Позвоните перед визитом",
    )

    markup = responses_keyboard((match,), "active")
    callback = markup.inline_keyboard[0][0].callback_data

    assert callback is not None
    data = ExecutorResponseCardCallback.unpack(callback)
    assert data.match_id == str(match_id)
    assert data.group == "active"


def test_response_card_text_contains_match_details() -> None:
    match = type(
        "Match",
        (),
        {
            "order_id": uuid4(),
            "service_name": "Прогулка",
            "starts_at": datetime(2026, 7, 31, 10, tzinfo=UTC),
            "ends_at": datetime(2026, 7, 31, 12, tzinfo=UTC),
            "response_expires_at": datetime(2026, 7, 31, 7, tzinfo=UTC),
            "status": "active",
            "total_amount": Decimal("1200.00"),
            "distance_km": Decimal("3.5"),
            "customer_comment": "Позвоните перед визитом",
        },
    )()

    text = response_card_text(match)

    assert "Карточка отклика" in text
    assert "Прогулка" in text
    assert "1200.00" in text
    assert "Позвоните перед визитом" in text


def test_response_card_has_back_to_order_button() -> None:
    order_id = str(uuid4())

    markup = response_card_keyboard("active", order_id)
    labels = [button.text for row in markup.inline_keyboard for button in row]

    assert "Назад к заказу" in labels
    back_button = next(
        button
        for row in markup.inline_keyboard
        for button in row
        if button.text == "Назад к заказу"
    )
    assert back_button.callback_data is not None
    callback = ExecutorOrderCardCallback.unpack(back_button.callback_data)
    assert callback.order_id == order_id


def test_direct_response_card_has_back_to_order_button() -> None:
    match_id = str(uuid4())
    order_id = str(uuid4())

    markup = direct_response_card_keyboard(match_id, order_id)
    back_button = next(
        button
        for row in markup.inline_keyboard
        for button in row
        if button.text == "Назад к заказу"
    )

    assert back_button.callback_data is not None
    callback = ExecutorOrderCardCallback.unpack(back_button.callback_data)
    assert callback.order_id == order_id
    assert callback.group == "direct"


@pytest.mark.asyncio
async def test_response_card_loads_match_instead_of_selected_order_card() -> None:
    performer_id = uuid4()
    match = OrderMatchDTO(
        id=uuid4(),
        order_id=uuid4(),
        performer_id=performer_id,
        source="pool",
        status="active",
        starts_at=datetime(2026, 7, 31, 10, tzinfo=UTC),
        ends_at=datetime(2026, 7, 31, 12, tzinfo=UTC),
        response_expires_at=datetime(2026, 7, 31, 7, tzinfo=UTC),
        selected_at=None,
        closed_at=None,
        close_reason=None,
        timezone="Europe/Moscow",
        service_name="Прогулка",
    )
    backend = AsyncMock()
    backend.get_registration_state.return_value = type(
        "State", (), {"performer": type("Performer", (), {"id": performer_id})()}
    )()
    backend.list_performer_responses.return_value = (match,)
    responder = AsyncMock()
    context = type("Context", (), {"telegram_id": 123})()

    await executor_response_card_callback(
        callback=object(),
        bot=object(),
        backend_client=backend,
        telegram_responder=responder,
        telegram_user_context=context,
        callback_data=ExecutorResponseCardCallback(
            match_id=str(match.id),
            group="active",
        ),
    )

    backend.get_performer_order_card.assert_not_awaited()
    responder.update.assert_awaited_once()
    assert "Карточка отклика" in responder.update.await_args.kwargs["text"]
    markup = responder.update.await_args.kwargs["reply_markup"]
    callback = markup.inline_keyboard[0][0].callback_data
    assert callback is not None
    assert ExecutorResponsesCallback.unpack(callback).group == "active"


def test_unavailable_period_time_parser_accepts_clock_values() -> None:
    assert _parse_time("09:30") is not None
    assert _parse_time("25:00") is None
    assert _parse_time("9:00") is None
    assert _parse_time("0900") is None
    assert _parse_time("09.30") is None
    assert _parse_time("09:30+03:00") is None


@pytest.mark.asyncio
async def test_unavailable_end_time_rejects_timezone_offset_without_crashing() -> None:
    backend = AsyncMock()
    responder = AsyncMock()
    state = AsyncMock()
    state.get_data.return_value = {
        "unavailable_start_date": "2026-08-06",
        "unavailable_end_date": "2026-08-07",
        "unavailable_start_time": "09:00",
    }
    context = type("Context", (), {"telegram_id": 123})()
    message = type("Message", (), {"text": "18:00+03:00"})()

    await save_unavailable_end_time(
        message=message,
        bot=object(),
        state=state,
        backend_client=backend,
        telegram_responder=responder,
        telegram_user_context=context,
    )

    backend.add_unavailable.assert_not_awaited()
    assert "формате ЧЧ:ММ" in responder.update.await_args.kwargs["text"]


@pytest.mark.asyncio
async def test_unavailable_backend_conflict_keeps_end_time_step() -> None:
    backend = AsyncMock()
    backend.add_unavailable.side_effect = BackendValidationError("conflict")
    responder = AsyncMock()
    state = AsyncMock()
    state.get_data.return_value = {
        "unavailable_start_date": "2026-08-06",
        "unavailable_end_date": "2026-08-07",
        "unavailable_start_time": "09:00",
    }
    context = type("Context", (), {"telegram_id": 123})()
    message = type("Message", (), {"text": "18:00"})()

    await save_unavailable_end_time(
        message=message,
        bot=object(),
        state=state,
        backend_client=backend,
        telegram_responder=responder,
        telegram_user_context=context,
    )

    state.clear.assert_not_awaited()
    state.set_state.assert_awaited_once()
    assert "Введите время окончания снова" in responder.update.await_args.kwargs[
        "text"
    ]


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
async def test_empty_executor_categories_show_waiting_message_without_keyboard() -> (
    None
):
    backend = AsyncMock()
    backend.list_catalog_categories.return_value = ()
    backend.list_performer_services.return_value = ()
    responder = AsyncMock()

    await show_category_select(
        bot=AsyncMock(),
        event=AsyncMock(),
        telegram_user_context=TelegramUserContext(
            telegram_id=123,
            username=None,
            chat_id=123,
        ),
        backend_client=backend,
        telegram_responder=responder,
    )

    responder.update.assert_awaited_once()
    kwargs = responder.update.await_args.kwargs
    assert kwargs["reply_markup"] is None
    assert "администратор добавит направление" in kwargs["text"].lower()


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


@pytest.mark.asyncio
async def test_avatar_upload_creates_new_menu_message() -> None:
    backend = AsyncMock()
    responder = AsyncMock()
    state = AsyncMock()
    context = type("Context", (), {"telegram_id": 123})()

    await _upload(
        message=object(),
        state=state,
        bot=object(),
        backend_client=backend,
        telegram_responder=responder,
        telegram_user_context=context,
        filename="avatar.jpg",
        content=b"image",
        content_type="image/jpeg",
    )

    assert responder.update.await_args.kwargs["create_new"] is True
    assert responder.update.await_args.kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_delete_current_work_address_shows_validation_error() -> None:
    address_id = uuid4()
    backend = AsyncMock()
    backend.delete_work_address.side_effect = BackendValidationError(
        "Current performer address cannot be deleted",
    )
    state = AsyncMock()
    state.get_data.return_value = {
        "work_addresses": [{"id": str(address_id)}],
    }
    responder = AsyncMock()
    context = type("Context", (), {"telegram_id": 123})()

    await delete_address(
        callback=object(),
        bot=object(),
        state=state,
        backend_client=backend,
        telegram_responder=responder,
        telegram_user_context=context,
        callback_data=WorkAddressDeleteCallback(index=0),
    )

    assert "нельзя удалить" in responder.update.await_args.kwargs["text"]

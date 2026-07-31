from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import CallbackQuery

from customer_bot.presentation.handlers.orders.schedule import (
    _set_start_at_and_ask_duration,
    enter_start,
)
from customer_bot.presentation.handlers.orders.state import parse_local_datetime


def test_parse_local_datetime_accepts_russian_format() -> None:
    value = parse_local_datetime("31.07.2099 10:00")

    assert value is not None
    assert value.strftime("%d.%m.%Y %H:%M") == "31.07.2099 10:00"


def test_parse_local_datetime_rejects_iso_format() -> None:
    assert parse_local_datetime("2099-07-31 10:00") is None


@pytest.mark.asyncio
async def test_invalid_manual_datetime_reprompts_with_combined_format() -> None:
    state = AsyncMock()
    state.get_data.return_value = {}
    responder = AsyncMock()

    await enter_start(
        message=SimpleNamespace(text="31/07/2099 10:00"),
        bot=object(),
        state=state,
        telegram_responder=responder,
        telegram_user_context=SimpleNamespace(telegram_id=123),
    )

    responder.update.assert_awaited_once()
    assert "ДД.ММ.ГГГГ ЧЧ:ММ" in responder.update.await_args.kwargs["text"]
    state.set_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_valid_manual_datetime_advances_to_duration() -> None:
    state = AsyncMock()
    state.get_data.return_value = {"order_draft": {"price_type": "hourly"}}
    responder = AsyncMock()

    await enter_start(
        message=SimpleNamespace(text="31.07.2099 10:00"),
        bot=object(),
        state=state,
        telegram_responder=responder,
        telegram_user_context=SimpleNamespace(telegram_id=123),
    )

    state.set_state.assert_awaited_once()
    assert "Длительность" in responder.update.await_args.kwargs["text"]


@pytest.mark.asyncio
async def test_past_manual_datetime_shows_past_message_without_fallback() -> None:
    state = AsyncMock()
    state.get_data.return_value = {}
    responder = AsyncMock()

    await enter_start(
        message=SimpleNamespace(text="01.01.2020 10:00"),
        bot=object(),
        state=state,
        telegram_responder=responder,
        telegram_user_context=SimpleNamespace(telegram_id=123),
    )

    responder.update.assert_awaited_once()
    text = responder.update.await_args.kwargs["text"]
    assert "Время уже прошло" in text
    assert "Выберите другое" in text
    assert "ДД.ММ.ГГГГ ЧЧ:ММ" in text
    assert responder.update.await_args.kwargs["create_new"] is True
    state.set_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_past_picker_time_keeps_time_picker() -> None:
    state = AsyncMock()
    state.get_data.return_value = {"order_start_date": "2020-01-01"}
    responder = AsyncMock()
    callback = CallbackQuery(
        id="callback-id",
        from_user={"id": 123, "is_bot": False, "first_name": "Test"},
        chat_instance="chat-instance",
    )

    await _set_start_at_and_ask_duration(
        callback,
        bot=object(),
        state=state,
        telegram_responder=responder,
        telegram_user_context=SimpleNamespace(telegram_id=123),
        start_at=datetime(2020, 1, 1, 10, 0),
    )

    responder.update.assert_awaited_once()
    update = responder.update.await_args.kwargs
    assert "Время уже прошло" in update["text"]
    assert "Время начала" in update["text"]
    assert update["reply_markup"] is not None
    assert update["create_new"] is True
    state.set_state.assert_not_awaited()

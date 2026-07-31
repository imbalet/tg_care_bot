from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from customer_bot.presentation.handlers.orders.schedule import enter_start
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

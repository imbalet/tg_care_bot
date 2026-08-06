from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from executor_bot.presentation.handlers.start import _open_start_or_menu


@pytest.mark.asyncio
async def test_start_shows_setup_hint_before_category_selection() -> None:
    backend = SimpleNamespace(
        get_registration_state=AsyncMock(
            return_value=SimpleNamespace(
                state="registered",
                performer=SimpleNamespace(
                    is_accepting_orders=False,
                    current_address_id=None,
                ),
            ),
        ),
        get_calendar=AsyncMock(return_value=SimpleNamespace(schedule=None)),
        list_performer_services=AsyncMock(return_value=()),
        list_catalog_categories=AsyncMock(return_value=()),
    )
    responder = AsyncMock()
    active_category_store = AsyncMock()
    active_category_store.get.return_value = None

    await _open_start_or_menu(
        message=object(),
        bot=object(),
        state=AsyncMock(),
        backend_client=backend,
        telegram_responder=responder,
        active_category_store=active_category_store,
        telegram_user_context=SimpleNamespace(telegram_id=123),
        start_registration_if_invited=True,
    )

    responder.send_notice.assert_awaited_once()
    assert "адрес" in responder.send_notice.await_args.kwargs["text"]
    responder.update.assert_awaited_once()
    assert "нет доступных направлений" in responder.update.await_args.kwargs[
        "text"
    ].lower()

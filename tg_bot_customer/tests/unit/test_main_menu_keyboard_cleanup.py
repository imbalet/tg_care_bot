from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from customer_bot.presentation.handlers.menu import main_menu_callback


@pytest.mark.asyncio
async def test_main_menu_does_not_send_keyboard_cleanup_message() -> None:
    backend = AsyncMock()
    backend.get_customer_profile.return_value = None
    backend.get_support_contact.return_value = None
    responder = AsyncMock()

    await main_menu_callback(
        callback=object(),
        bot=object(),
        backend_client=backend,
        active_category_store=AsyncMock(),
        telegram_responder=responder,
        telegram_user_context=SimpleNamespace(telegram_id=123),
    )

    responder.clear_reply_keyboard.assert_not_awaited()

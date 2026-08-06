from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from executor_bot.presentation.handlers.fallback import main_menu_callback


@pytest.mark.asyncio
async def test_main_menu_does_not_send_keyboard_cleanup_message() -> None:
    backend = AsyncMock()
    backend.get_registration_state.return_value = SimpleNamespace(
        state="no_invitation",
        performer=None,
    )
    responder = AsyncMock()

    await main_menu_callback(
        callback=SimpleNamespace(message=None),
        bot=object(),
        backend_client=backend,
        active_category_store=AsyncMock(),
        telegram_responder=responder,
        telegram_user_context=SimpleNamespace(telegram_id=123),
    )

    responder.clear_reply_keyboard.assert_not_awaited()

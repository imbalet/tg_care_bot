import logging
from datetime import UTC, datetime

import pytest
from aiogram.types import Chat, ErrorEvent, Message, Update, User

from customer_bot.presentation.error_handler import handle_unexpected_error


@pytest.mark.asyncio
async def test_unexpected_error_handler_logs_safe_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    update = Update(
        update_id=10,
        message=Message(
            message_id=20,
            date=datetime(2026, 1, 1, tzinfo=UTC),
            chat=Chat(id=30, type="private"),
            from_user=User(id=40, is_bot=False, first_name="Private"),
            text="secret text",
        ),
    )

    with caplog.at_level(logging.ERROR):
        handled = await handle_unexpected_error(
            ErrorEvent(update=update, exception=RuntimeError("boom")),
        )

    assert handled is True
    assert "Unhandled Telegram update error" in caplog.text
    assert "secret text" not in caplog.text
    assert "Private" not in caplog.text

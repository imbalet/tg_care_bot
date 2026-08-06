from datetime import UTC, datetime
from unittest.mock import AsyncMock

from aiogram.types import Chat, InlineKeyboardMarkup, Message, ReplyKeyboardRemove

from executor_bot.presentation.services.telegram_responder import TelegramResponder


def _telegram_message(message_id: int) -> Message:
    return Message(
        message_id=message_id,
        date=datetime.now(UTC),
        chat=Chat(id=123, type="private"),
        text="menu",
    )


async def test_cleanup_uses_visible_screen_and_not_invisible_message() -> None:
    bot = AsyncMock()
    bot.send_message.return_value = _telegram_message(2)
    store = AsyncMock()
    responder = TelegramResponder(message_store=store)

    await responder.update(
        bot=bot,
        event=_telegram_message(1),
        telegram_id=123,
        text="Главное меню",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[]),
        clear_reply_keyboard=True,
    )

    sent_kwargs = bot.send_message.await_args.kwargs
    assert sent_kwargs["text"] == "Главное меню"
    assert isinstance(sent_kwargs["reply_markup"], ReplyKeyboardRemove)
    bot.edit_message_text.assert_awaited_once()

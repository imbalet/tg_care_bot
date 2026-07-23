from collections.abc import Awaitable, Callable
from typing import Any, cast

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, InaccessibleMessage, TelegramObject


class CallbackMessageMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)

        if event.message is None:
            await event.answer("Сообщение не найдено", show_alert=True)
            return None

        if isinstance(event.message, InaccessibleMessage):
            bot = data.get("bot")
            if isinstance(bot, Bot):
                await bot.send_message(
                    chat_id=event.message.chat.id,
                    text="Сообщение недоступно",
                )
            await event.answer()
            return None

        return await handler(cast(TelegramObject, event), data)


__all__ = ["CallbackMessageMiddleware"]

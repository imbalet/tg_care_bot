from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User


@dataclass(frozen=True)
class TelegramUserContext:
    telegram_id: int
    username: str | None
    chat_id: int | None
    message_thread_id: int | None


class TelegramUserContextMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        event_from_user = data.get("event_from_user")
        if isinstance(event_from_user, User):
            chat_id: int | None = None
            message_thread_id: int | None = None
            if isinstance(event, Message):
                chat_id = event.chat.id
                message_thread_id = event.message_thread_id
            elif isinstance(event, CallbackQuery) and isinstance(
                event.message, Message
            ):
                chat_id = event.message.chat.id
                message_thread_id = event.message.message_thread_id
            data["telegram_user_context"] = TelegramUserContext(
                telegram_id=event_from_user.id,
                username=event_from_user.username,
                chat_id=chat_id,
                message_thread_id=message_thread_id,
            )
        return await handler(event, data)


__all__ = ["TelegramUserContext", "TelegramUserContextMiddleware"]

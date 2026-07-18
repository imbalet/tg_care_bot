from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, User

from executor_bot.presentation.contexts import TelegramUserContext

from .helpers import set_telegram_user_context


class TelegramUserContextMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        event_from_user = data.get("event_from_user")
        if isinstance(event_from_user, User) and isinstance(event, Update):
            chat_id: int | None = None

            if event.message and event.message.from_user:
                chat_id = event.message.chat.id
            elif event.callback_query and event.callback_query.from_user.id:
                chat_id = (
                    event.callback_query.message.chat.id
                    if event.callback_query.message
                    else None
                )
            set_telegram_user_context(
                data=data,
                user_context=TelegramUserContext(
                    telegram_id=event_from_user.id,
                    username=event_from_user.username,
                    chat_id=chat_id,
                ),
            )
        else:
            return None

        return await handler(event, data)


__all__ = ["TelegramUserContext", "TelegramUserContextMiddleware"]

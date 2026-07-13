from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from .helpers import get_app_context


class AppContextMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        app_context = get_app_context(data)
        data["backend_client"] = app_context.backend_client
        data["menu_manager"] = app_context.menu_manager
        data["topic_setup_service"] = app_context.topic_setup_service
        data["username_sync_service"] = app_context.username_sync_service
        return await handler(event, data)

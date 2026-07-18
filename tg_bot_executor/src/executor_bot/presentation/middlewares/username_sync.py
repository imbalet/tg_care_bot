from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from executor_bot.application.services import (
    ABSENT_USERNAME,
    USERNAME_SYNC_TTL_SECONDS,
    UsernameSyncService,
)
from executor_bot.presentation.contexts import TelegramUserContext

from .helpers import get_app_context, get_telegram_user_context

__all__ = [
    "ABSENT_USERNAME",
    "USERNAME_SYNC_TTL_SECONDS",
    "TelegramUsernameSyncMiddleware",
]


class TelegramUsernameSyncMiddleware(BaseMiddleware):
    def __init__(self, service: UsernameSyncService | None = None) -> None:
        self._service = service

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        context = get_telegram_user_context(data)
        service = self._service or get_app_context(data).username_sync_service
        await self.sync(context, service)
        return await handler(event, data)

    async def sync(
        self,
        context: TelegramUserContext,
        service: UsernameSyncService,
    ) -> None:
        await service.sync(
            telegram_id=context.telegram_id,
            username=context.username,
        )

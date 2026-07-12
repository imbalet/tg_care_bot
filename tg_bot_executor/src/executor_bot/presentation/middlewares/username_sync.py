from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from redis.asyncio import Redis

from executor_bot.infrastructure.http import BackendClient, BackendClientError
from executor_bot.infrastructure.redis import executor_redis_keys
from executor_bot.presentation.middlewares.user_context import TelegramUserContext

ABSENT_USERNAME = "<absent>"
USERNAME_SYNC_TTL_SECONDS = 600


class TelegramUsernameSyncMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        context = data.get("telegram_user_context")
        backend_client = data.get("backend_client")
        if isinstance(context, TelegramUserContext) and isinstance(
            backend_client,
            BackendClient,
        ):
            await self.sync(context, backend_client)
        return await handler(event, data)

    async def sync(
        self,
        context: TelegramUserContext,
        backend_client: BackendClient,
    ) -> None:
        key = executor_redis_keys.username_sync_cache(context.telegram_id)
        current = _cache_value(context.username)
        cached = await self._redis.get(key)
        if cached == current:
            return
        try:
            await backend_client.update_performer_username(
                telegram_id=context.telegram_id,
                telegram_username=context.username,
            )
        except BackendClientError:
            return
        await self._redis.set(key, current, ex=USERNAME_SYNC_TTL_SECONDS)


def _cache_value(username: str | None) -> str:
    return username if username is not None else ABSENT_USERNAME


__all__ = [
    "ABSENT_USERNAME",
    "TelegramUsernameSyncMiddleware",
    "USERNAME_SYNC_TTL_SECONDS",
]

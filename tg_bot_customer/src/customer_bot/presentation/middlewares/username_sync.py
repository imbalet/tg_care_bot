from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from redis.asyncio import Redis

from customer_bot.infrastructure.http import BackendClient, BackendClientError
from customer_bot.infrastructure.redis import customer_redis_keys
from customer_bot.presentation.contexts import TelegramUserContext

from .helpers import get_app_context, get_telegram_user_context

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
        context = get_telegram_user_context(data)
        backend_client = get_app_context(data).backend_client
        if isinstance(backend_client, BackendClient):
            await self.sync(context, backend_client)
        return await handler(event, data)

    async def sync(
        self,
        context: TelegramUserContext,
        backend_client: BackendClient,
    ) -> None:
        key = customer_redis_keys.username_sync_cache(context.telegram_id)
        current = _normalize_value(context.username)
        cached = await self._redis.get(key)
        if cached == current:
            return
        try:
            await backend_client.update_customer_username(
                telegram_id=context.telegram_id,
                telegram_username=context.username,
            )
        except BackendClientError:
            return
        await self._redis.set(key, current, ex=USERNAME_SYNC_TTL_SECONDS)


def _normalize_value(username: str | None) -> str:
    return username if username is not None else ABSENT_USERNAME

import logging
from time import time

from redis.asyncio import Redis

from executor_bot.application.ports import (
    ActiveCategoryStore,
    CurrentMessageStore,
    UsernameSyncCache,
    ViewedAvailableOrdersStore,
)

from .keys import ExecutorRedisKeys, executor_redis_keys

logger = logging.getLogger(__name__)


class RedisUsernameSyncCache(UsernameSyncCache):
    def __init__(
        self,
        redis: Redis,
        keys: ExecutorRedisKeys = executor_redis_keys,
    ) -> None:
        self._redis = redis
        self._keys = keys

    async def get(self, telegram_id: int) -> str | None:
        value = await self._redis.get(self._keys.username_sync_cache(telegram_id))
        return value if isinstance(value, str) else None

    async def set(self, telegram_id: int, value: str, ttl_seconds: int) -> None:
        await self._redis.set(
            self._keys.username_sync_cache(telegram_id),
            value,
            ex=ttl_seconds,
        )


class RedisActiveCategoryStore(ActiveCategoryStore):
    def __init__(
        self,
        redis: Redis,
        keys: ExecutorRedisKeys = executor_redis_keys,
    ) -> None:
        self._redis = redis
        self._keys = keys

    async def get(self, telegram_id: int) -> str | None:
        value = await self._redis.get(self._keys.active_category(telegram_id))
        return value if isinstance(value, str) and value else None

    async def set(self, telegram_id: int, category_code: str) -> None:
        await self._redis.set(self._keys.active_category(telegram_id), category_code)


class RedisCurrentMessageStore(CurrentMessageStore):
    def __init__(
        self,
        redis: Redis,
        keys: ExecutorRedisKeys = executor_redis_keys,
    ) -> None:
        self._redis = redis
        self._keys = keys

    async def get(self, telegram_id: int) -> int | None:
        key = self._keys.current_message(telegram_id)
        value = await self._redis.get(key)
        if not isinstance(value, str):
            return None
        try:
            return int(value)
        except ValueError:
            logger.warning(
                "Invalid screen message id in Redis",
                extra={"telegram_id": telegram_id},
            )
            await self._redis.delete(key)
            return None

    async def set(self, telegram_id: int, message_id: int) -> None:
        await self._redis.set(
            self._keys.current_message(telegram_id),
            message_id,
        )

    async def delete(self, telegram_id: int) -> None:
        await self._redis.delete(self._keys.current_message(telegram_id))


class RedisViewedAvailableOrdersStore(ViewedAvailableOrdersStore):
    def __init__(
        self,
        redis: Redis,
        keys: ExecutorRedisKeys = executor_redis_keys,
    ) -> None:
        self._redis = redis
        self._keys = keys

    async def list_viewed(self, telegram_id: int) -> set[str]:
        values = await self._redis.zrange(
            self._keys.viewed_available_orders(telegram_id),
            0,
            -1,
        )
        return {value for value in values if isinstance(value, str)}

    async def mark_viewed(self, telegram_id: int, order_id: str) -> None:
        await self._redis.zadd(
            self._keys.viewed_available_orders(telegram_id),
            {order_id: time()},
        )

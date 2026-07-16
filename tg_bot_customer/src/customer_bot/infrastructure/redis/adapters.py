import logging

from customer_bot.application.ports import (
    ActiveCategoryStore,
    ScreenMessageStore,
    UsernameSyncCache,
)
from redis.asyncio import Redis

from .keys import CustomerRedisKeys, customer_redis_keys

logger = logging.getLogger(__name__)


class RedisUsernameSyncCache(UsernameSyncCache):
    def __init__(
        self,
        redis: Redis,
        keys: CustomerRedisKeys = customer_redis_keys,
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
        keys: CustomerRedisKeys = customer_redis_keys,
    ) -> None:
        self._redis = redis
        self._keys = keys

    async def get(self, telegram_id: int) -> str | None:
        value = await self._redis.get(self._keys.active_category(telegram_id))
        return value if isinstance(value, str) and value else None

    async def set(self, telegram_id: int, category_code: str) -> None:
        await self._redis.set(self._keys.active_category(telegram_id), category_code)


class RedisScreenMessageStore(ScreenMessageStore):
    def __init__(
        self,
        redis: Redis,
        keys: CustomerRedisKeys = customer_redis_keys,
    ) -> None:
        self._redis = redis
        self._keys = keys

    async def get(self, telegram_id: int, screen_key: str) -> int | None:
        value = await self._redis.get(
            self._keys.screen_message(telegram_id, screen_key)
        )
        if not isinstance(value, str):
            return None
        try:
            return int(value)
        except ValueError:
            logger.warning(
                "Invalid screen message id in Redis",
                extra={"telegram_id": telegram_id, "screen_key": screen_key},
            )
            await self.delete(telegram_id, screen_key)
            return None

    async def set(self, telegram_id: int, screen_key: str, message_id: int) -> None:
        await self._redis.set(
            self._keys.screen_message(telegram_id, screen_key),
            message_id,
        )

    async def delete(self, telegram_id: int, screen_key: str) -> None:
        await self._redis.delete(self._keys.screen_message(telegram_id, screen_key))

import logging

from customer_bot.application.ports import (
    ActiveCategoryStore,
    CurrentMessageStore,
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


class RedisCurrentMessageStore(CurrentMessageStore):
    def __init__(
        self,
        redis: Redis,
        keys: CustomerRedisKeys = customer_redis_keys,
    ) -> None:
        self._redis = redis
        self._keys = keys

    async def get(self, telegram_id: int) -> int | None:
        current_key = self._keys.current_message(telegram_id)
        value = await self._redis.get(current_key)
        message_id = await self._parse_message_id(telegram_id, current_key, value)
        if message_id is not None:
            return message_id

        legacy_key = self._keys.legacy_screen_message(telegram_id, "main")
        legacy_value = await self._redis.get(legacy_key)
        legacy_message_id = await self._parse_message_id(
            telegram_id,
            legacy_key,
            legacy_value,
        )
        if legacy_message_id is not None:
            await self.set(telegram_id, legacy_message_id)
        return legacy_message_id

    async def set(self, telegram_id: int, message_id: int) -> None:
        await self._redis.set(
            self._keys.current_message(telegram_id),
            message_id,
        )

    async def delete(self, telegram_id: int) -> None:
        await self._redis.delete(self._keys.current_message(telegram_id))

    async def _parse_message_id(
        self,
        telegram_id: int,
        key: str,
        value: object,
    ) -> int | None:
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

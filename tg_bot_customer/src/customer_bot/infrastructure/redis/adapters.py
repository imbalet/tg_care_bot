from redis.asyncio import Redis

from .keys import CustomerRedisKeys, customer_redis_keys


class RedisUsernameSyncCache:
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


class RedisActiveCategoryStore:
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


class RedisMenuMessageStore:
    def __init__(
        self,
        redis: Redis,
        keys: CustomerRedisKeys = customer_redis_keys,
    ) -> None:
        self._redis = redis
        self._keys = keys

    async def get(self, telegram_id: int, topic_key: str) -> int | None:
        value = await self._redis.get(self._keys.menu_message(telegram_id, topic_key))
        if not isinstance(value, str):
            return None
        try:
            return int(value)
        except ValueError:
            await self.delete(telegram_id, topic_key)
            return None

    async def set(self, telegram_id: int, topic_key: str, message_id: int) -> None:
        await self._redis.set(
            self._keys.menu_message(telegram_id, topic_key),
            message_id,
        )

    async def delete(self, telegram_id: int, topic_key: str) -> None:
        await self._redis.delete(self._keys.menu_message(telegram_id, topic_key))

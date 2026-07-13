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


class RedisTopicCache:
    def __init__(
        self,
        redis: Redis,
        keys: CustomerRedisKeys = customer_redis_keys,
    ) -> None:
        self._redis = redis
        self._keys = keys

    async def topic_kind_by_thread(
        self,
        telegram_id: int,
        message_thread_id: int | None,
    ) -> str:
        if message_thread_id is None:
            return "general"
        value = await self._redis.get(
            self._keys.topic_kind_by_thread(telegram_id, message_thread_id)
        )
        return value if isinstance(value, str) and value else "general"

    async def save_topic_thread(
        self,
        *,
        telegram_id: int,
        topic_kind: str,
        message_thread_id: int | None,
    ) -> None:
        if message_thread_id is None:
            await self._redis.set(
                self._keys.topic_thread_by_kind(telegram_id, topic_kind),
                "",
            )
            return
        await self._redis.set(
            self._keys.topic_kind_by_thread(telegram_id, message_thread_id),
            topic_kind,
        )
        await self._redis.set(
            self._keys.topic_thread_by_kind(telegram_id, topic_kind),
            message_thread_id,
        )


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

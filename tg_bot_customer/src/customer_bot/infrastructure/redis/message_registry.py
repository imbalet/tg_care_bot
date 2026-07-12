from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True)
class RegisteredMessage:
    chat_id: int
    message_id: int
    message_thread_id: int | None = None


class MessageRegistry:
    def __init__(self, redis: Redis, prefix: str = "customer_bot:messages") -> None:
        self._redis = redis
        self._prefix = prefix

    async def register(self, semantic_key: str, message: RegisteredMessage) -> None:
        value = (
            f"{message.chat_id}:{message.message_id}:{message.message_thread_id or ''}"
        )
        await self._redis.set(self._key(semantic_key), value)

    async def remove(self, semantic_key: str) -> None:
        await self._redis.delete(self._key(semantic_key))

    def _key(self, semantic_key: str) -> str:
        return f"{self._prefix}:{semantic_key}"


__all__ = ["MessageRegistry", "RegisteredMessage"]

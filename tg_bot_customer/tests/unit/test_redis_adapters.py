import logging

import pytest

from customer_bot.infrastructure.redis.adapters import RedisScreenMessageStore


class FakeRedis:
    def __init__(self, value: str | None) -> None:
        self.value = value
        self.deleted: list[str] = []

    async def get(self, _key: str) -> str | None:
        return self.value

    async def set(self, _key: str, value: int) -> None:
        self.value = str(value)

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.value = None


@pytest.mark.asyncio
async def test_screen_message_store_logs_invalid_message_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    redis = FakeRedis("not-int")
    store = RedisScreenMessageStore(redis)  # type: ignore[arg-type]

    with caplog.at_level(logging.WARNING):
        result = await store.get(telegram_id=123, screen_key="main")

    assert result is None
    assert "Invalid screen message id in Redis" in caplog.text
    assert redis.deleted

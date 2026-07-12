from typing import Any, cast

import pytest

from executor_bot.infrastructure.http import BackendUnavailableError
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.middlewares.username_sync import (
    ABSENT_USERNAME,
    USERNAME_SYNC_TTL_SECONDS,
    TelegramUsernameSyncMiddleware,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int) -> None:
        self.values[key] = value
        self.ttl[key] = ex


class FakeBackendClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[int, str | None]] = []

    async def update_performer_username(
        self,
        *,
        telegram_id: int,
        telegram_username: str | None,
    ) -> None:
        if self.fail:
            raise BackendUnavailableError("Backend unavailable")
        self.calls.append((telegram_id, telegram_username))


def context(username: str | None) -> TelegramUserContext:
    return TelegramUserContext(
        telegram_id=123,
        username=username,
        chat_id=456,
        message_thread_id=None,
    )


@pytest.mark.asyncio
async def test_username_sync_updates_cache_after_success() -> None:
    redis = FakeRedis()
    backend = FakeBackendClient()
    middleware = TelegramUsernameSyncMiddleware(cast(Any, redis))

    await middleware.sync(context("new_name"), cast(Any, backend))

    assert backend.calls == [(123, "new_name")]
    assert list(redis.values.values()) == ["new_name"]
    assert list(redis.ttl.values()) == [USERNAME_SYNC_TTL_SECONDS]


@pytest.mark.asyncio
async def test_username_sync_sends_null_for_absent_username() -> None:
    redis = FakeRedis()
    backend = FakeBackendClient()
    middleware = TelegramUsernameSyncMiddleware(cast(Any, redis))

    await middleware.sync(context(None), cast(Any, backend))

    assert backend.calls == [(123, None)]
    assert list(redis.values.values()) == [ABSENT_USERNAME]


@pytest.mark.asyncio
async def test_username_sync_skips_when_cache_matches() -> None:
    redis = FakeRedis()
    redis.values["executor_bot:username_sync:123"] = "same"
    backend = FakeBackendClient()
    middleware = TelegramUsernameSyncMiddleware(cast(Any, redis))

    await middleware.sync(context("same"), cast(Any, backend))

    assert backend.calls == []


@pytest.mark.asyncio
async def test_username_sync_does_not_update_cache_after_failure() -> None:
    redis = FakeRedis()
    backend = FakeBackendClient(fail=True)
    middleware = TelegramUsernameSyncMiddleware(cast(Any, redis))

    await middleware.sync(context("new_name"), cast(Any, backend))

    assert redis.values == {}

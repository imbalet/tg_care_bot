from typing import Any, cast

import pytest

from customer_bot.application.errors import BackendUnavailableError
from customer_bot.application.services import UsernameSyncService
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.middlewares.username_sync import (
    ABSENT_USERNAME,
    USERNAME_SYNC_TTL_SECONDS,
    TelegramUsernameSyncMiddleware,
)


class FakeUsernameSyncCache:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    async def get(self, telegram_id: int) -> str | None:
        return self.values.get(str(telegram_id))

    async def set(self, telegram_id: int, value: str, ttl_seconds: int) -> None:
        self.values[str(telegram_id)] = value
        self.ttl[str(telegram_id)] = ttl_seconds


class FakeBackendClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[int, str | None]] = []

    async def update_customer_username(
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
    )


@pytest.mark.asyncio
async def test_username_sync_updates_cache_after_success() -> None:
    cache = FakeUsernameSyncCache()
    backend = FakeBackendClient()
    service = UsernameSyncService(backend=cast(Any, backend), cache=cache)
    middleware = TelegramUsernameSyncMiddleware()

    await middleware.sync(context("new_name"), service)

    assert backend.calls == [(123, "new_name")]
    assert list(cache.values.values()) == ["new_name"]
    assert list(cache.ttl.values()) == [USERNAME_SYNC_TTL_SECONDS]


@pytest.mark.asyncio
async def test_username_sync_sends_null_for_absent_username() -> None:
    cache = FakeUsernameSyncCache()
    backend = FakeBackendClient()
    service = UsernameSyncService(backend=cast(Any, backend), cache=cache)
    middleware = TelegramUsernameSyncMiddleware()

    await middleware.sync(context(None), service)

    assert backend.calls == [(123, None)]
    assert list(cache.values.values()) == [ABSENT_USERNAME]


@pytest.mark.asyncio
async def test_username_sync_skips_when_cache_matches() -> None:
    cache = FakeUsernameSyncCache()
    cache.values["123"] = "same"
    backend = FakeBackendClient()
    service = UsernameSyncService(backend=cast(Any, backend), cache=cache)
    middleware = TelegramUsernameSyncMiddleware()

    await middleware.sync(context("same"), service)

    assert backend.calls == []


@pytest.mark.asyncio
async def test_username_sync_does_not_update_cache_after_failure() -> None:
    cache = FakeUsernameSyncCache()
    backend = FakeBackendClient(fail=True)
    service = UsernameSyncService(backend=cast(Any, backend), cache=cache)
    middleware = TelegramUsernameSyncMiddleware()

    await middleware.sync(context("new_name"), service)

    assert cache.values == {}

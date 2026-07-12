from typing import Any, cast
from uuid import uuid4

import pytest

from backend.modules.admin.infrastructure import (
    Argon2PasswordHasher,
    RedisAdminSessionStore,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int) -> None:
        self.values[key] = value

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


def test_argon2_password_hasher_verifies_password() -> None:
    hasher = Argon2PasswordHasher()

    password_hash = hasher.hash("secret-password")

    assert hasher.verify(password_hash, "secret-password") is True


def test_argon2_password_hasher_rejects_wrong_password() -> None:
    hasher = Argon2PasswordHasher()

    password_hash = hasher.hash("secret-password")

    assert hasher.verify(password_hash, "wrong-password") is False


@pytest.mark.asyncio
async def test_redis_admin_session_store_creates_reads_and_deletes_session() -> None:
    redis = FakeRedis()
    store = RedisAdminSessionStore(redis=cast(Any, redis), ttl_seconds=60)
    admin_id = uuid4()

    session = await store.create(admin_id)

    restored = await store.get(session.session_id)
    assert restored == session

    await store.delete(session.session_id)

    assert await store.get(session.session_id) is None

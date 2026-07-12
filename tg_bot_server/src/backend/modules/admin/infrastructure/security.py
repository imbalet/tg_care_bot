import json
import secrets
from uuid import UUID

from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from redis.asyncio import Redis

from backend.common.infrastructure import backend_redis_keys
from backend.modules.admin.application import AdminSession


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._hasher = Argon2Hasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except VerificationError, VerifyMismatchError:
            return False


class RedisAdminSessionStore:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    async def create(self, admin_id: UUID) -> AdminSession:
        session = AdminSession(
            session_id=secrets.token_urlsafe(32),
            admin_id=admin_id,
            csrf_token=secrets.token_urlsafe(32),
        )
        await self._redis.set(
            backend_redis_keys.admin_session(session.session_id),
            json.dumps(
                {
                    "admin_id": str(session.admin_id),
                    "csrf_token": session.csrf_token,
                },
            ),
            ex=self._ttl_seconds,
        )
        return session

    async def get(self, session_id: str) -> AdminSession | None:
        raw = await self._redis.get(backend_redis_keys.admin_session(session_id))
        if raw is None:
            return None
        data = json.loads(raw)
        return AdminSession(
            session_id=session_id,
            admin_id=UUID(data["admin_id"]),
            csrf_token=data["csrf_token"],
        )

    async def delete(self, session_id: str) -> None:
        await self._redis.delete(backend_redis_keys.admin_session(session_id))


__all__ = ["Argon2PasswordHasher", "RedisAdminSessionStore"]

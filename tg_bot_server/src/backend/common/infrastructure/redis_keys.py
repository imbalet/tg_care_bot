from dataclasses import dataclass


@dataclass(frozen=True)
class RedisKeyNamespace:
    prefix: str

    def admin_session(self, session_id: str) -> str:
        return self._join("admin", "sessions", session_id)

    def technical_cache(self, key: str) -> str:
        return self._join("cache", "technical", key)

    def rate_limit(self, scope: str, identity: str) -> str:
        return self._join("rate_limit", scope, identity)

    def _join(self, *parts: str) -> str:
        return ":".join((self.prefix, *parts))


backend_redis_keys = RedisKeyNamespace(prefix="backend")


__all__ = ["RedisKeyNamespace", "backend_redis_keys"]

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutorRedisKeys:
    prefix: str = "executor_bot"

    def ui_state(self, telegram_id: int, key: str) -> str:
        return self._join("ui_state", str(telegram_id), key)

    def viewed_available_orders(self, telegram_id: int) -> str:
        return self._join("ui_state", str(telegram_id), "viewed_available_orders")

    def username_sync_cache(self, telegram_id: int) -> str:
        return self._join("username_sync", str(telegram_id))

    def _join(self, *parts: str) -> str:
        return ":".join((self.prefix, *parts))


executor_redis_keys = ExecutorRedisKeys()


__all__ = ["ExecutorRedisKeys", "executor_redis_keys"]

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

    def active_category(self, telegram_id: int) -> str:
        return f"tg:performer:{telegram_id}:active_category"

    def current_message(self, telegram_id: int) -> str:
        return self._join("screen", str(telegram_id), "current")

    def menu_message(self, telegram_id: int) -> str:
        return self.current_message(telegram_id)

    def _join(self, *parts: str) -> str:
        return ":".join((self.prefix, *parts))


executor_redis_keys = ExecutorRedisKeys()


__all__ = ["ExecutorRedisKeys", "executor_redis_keys"]

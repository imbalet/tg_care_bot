from dataclasses import dataclass


@dataclass(frozen=True)
class CustomerRedisKeys:
    prefix: str = "customer_bot"

    def ui_state(self, telegram_id: int, key: str) -> str:
        return self._join("ui_state", str(telegram_id), key)

    def viewed_available_orders(self, telegram_id: int) -> str:
        return self._join("ui_state", str(telegram_id), "viewed_available_orders")

    def username_sync_cache(self, telegram_id: int) -> str:
        return self._join("username_sync", str(telegram_id))

    def topic_kind_by_thread(self, telegram_id: int, message_thread_id: int) -> str:
        return self._join("topics", str(telegram_id), "thread", str(message_thread_id))

    def topic_thread_by_kind(self, telegram_id: int, topic_kind: str) -> str:
        return self._join("topics", str(telegram_id), "kind", topic_kind)

    def menu_message(self, telegram_id: int, topic_key: str) -> str:
        return self._join("menu", str(telegram_id), topic_key)

    def _join(self, *parts: str) -> str:
        return ":".join((self.prefix, *parts))


customer_redis_keys = CustomerRedisKeys()


__all__ = ["CustomerRedisKeys", "customer_redis_keys"]

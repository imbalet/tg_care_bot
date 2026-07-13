from typing import Protocol


class UsernameSyncCache(Protocol):
    async def get(self, telegram_id: int) -> str | None: ...

    async def set(self, telegram_id: int, value: str, ttl_seconds: int) -> None: ...


class TopicCache(Protocol):
    async def topic_kind_by_thread(
        self,
        telegram_id: int,
        message_thread_id: int | None,
    ) -> str: ...

    async def save_topic_thread(
        self,
        *,
        telegram_id: int,
        topic_kind: str,
        message_thread_id: int | None,
    ) -> None: ...


class MenuMessageStore(Protocol):
    async def get(self, telegram_id: int, topic_key: str) -> int | None: ...

    async def set(self, telegram_id: int, topic_key: str, message_id: int) -> None: ...

    async def delete(self, telegram_id: int, topic_key: str) -> None: ...

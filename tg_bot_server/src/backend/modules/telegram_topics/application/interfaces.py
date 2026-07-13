from typing import Protocol
from uuid import UUID

from backend.modules.telegram_topics.application.dto import TelegramTopicDTO


class TelegramTopicRepository(Protocol):
    async def get_owner_id(self, *, account_type: str, telegram_id: int) -> UUID | None:
        pass

    async def ensure_topics(
        self,
        *,
        account_type: str,
        owner_id: UUID,
        chat_id: int,
        topic_kinds: tuple[str, ...],
    ) -> tuple[TelegramTopicDTO, ...]:
        pass

    async def update_mapping(
        self,
        *,
        topic_id: UUID,
        chat_id: int,
        message_thread_id: int | None,
        status: str,
    ) -> TelegramTopicDTO | None:
        pass


__all__ = ["TelegramTopicRepository"]

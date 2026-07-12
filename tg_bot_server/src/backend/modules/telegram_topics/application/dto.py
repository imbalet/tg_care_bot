from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TelegramTopicDTO:
    id: UUID
    account_type: str
    owner_id: UUID
    topic_kind: str
    chat_id: int
    message_thread_id: int | None
    status: str


__all__ = ["TelegramTopicDTO"]

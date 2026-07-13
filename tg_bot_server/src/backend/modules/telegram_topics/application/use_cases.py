from dataclasses import dataclass
from uuid import UUID

from backend.common.domain import NotFoundError, ValidationError
from backend.modules.telegram_topics.application.dto import TelegramTopicDTO
from backend.modules.telegram_topics.application.interfaces import (
    TelegramTopicRepository,
)

CUSTOMER_TOPIC_KINDS = ("children", "wards", "pets", "notifications")
PERFORMER_TOPIC_KINDS = ("work", "notifications")


def topic_kinds_for(account_type: str) -> tuple[str, ...]:
    if account_type == "customer":
        return CUSTOMER_TOPIC_KINDS
    if account_type == "performer":
        return PERFORMER_TOPIC_KINDS
    raise ValidationError("Account type is invalid")


@dataclass(frozen=True)
class EnsureTelegramTopicsCommand:
    account_type: str
    telegram_id: int
    chat_id: int


class EnsureTelegramTopicsUseCase:
    def __init__(self, repository: TelegramTopicRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        command: EnsureTelegramTopicsCommand,
    ) -> tuple[TelegramTopicDTO, ...]:
        topic_kinds = topic_kinds_for(command.account_type)
        owner_id = await self._repository.get_owner_id(
            account_type=command.account_type,
            telegram_id=command.telegram_id,
        )
        if owner_id is None:
            raise NotFoundError("Telegram account owner not found")
        return await self._repository.ensure_topics(
            account_type=command.account_type,
            owner_id=owner_id,
            chat_id=command.chat_id,
            topic_kinds=topic_kinds,
        )


@dataclass(frozen=True)
class UpdateTelegramTopicMappingCommand:
    topic_id: UUID
    chat_id: int
    message_thread_id: int | None
    status: str


class UpdateTelegramTopicMappingUseCase:
    def __init__(self, repository: TelegramTopicRepository) -> None:
        self._repository = repository

    async def execute(
        self, command: UpdateTelegramTopicMappingCommand
    ) -> TelegramTopicDTO:
        if command.status not in {"active", "fallback", "unavailable"}:
            raise ValidationError("Telegram topic status is invalid")
        topic = await self._repository.update_mapping(
            topic_id=command.topic_id,
            chat_id=command.chat_id,
            message_thread_id=command.message_thread_id,
            status=command.status,
        )
        if topic is None:
            raise NotFoundError("Telegram topic not found")
        return topic


__all__ = [
    "CUSTOMER_TOPIC_KINDS",
    "EnsureTelegramTopicsCommand",
    "EnsureTelegramTopicsUseCase",
    "PERFORMER_TOPIC_KINDS",
    "UpdateTelegramTopicMappingCommand",
    "UpdateTelegramTopicMappingUseCase",
    "topic_kinds_for",
]

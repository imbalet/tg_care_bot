from uuid import UUID, uuid4

import pytest

from backend.common.domain import NotFoundError, ValidationError
from backend.modules.telegram_topics.application import (
    CUSTOMER_TOPIC_KINDS,
    EnsureTelegramTopicsCommand,
    EnsureTelegramTopicsUseCase,
    PERFORMER_TOPIC_KINDS,
    TelegramTopicDTO,
    UpdateTelegramTopicMappingCommand,
    UpdateTelegramTopicMappingUseCase,
)


class FakeTelegramTopicRepository:
    def __init__(self) -> None:
        self.owner_id = uuid4()
        self.topics: dict[UUID, TelegramTopicDTO] = {}

    async def get_owner_id(self, *, account_type: str, telegram_id: int) -> UUID | None:
        if telegram_id == 404:
            return None
        return self.owner_id

    async def ensure_topics(
        self,
        *,
        account_type: str,
        owner_id: UUID,
        chat_id: int,
        topic_kinds: tuple[str, ...],
    ) -> tuple[TelegramTopicDTO, ...]:
        if not self.topics:
            for topic_kind in topic_kinds:
                topic = TelegramTopicDTO(
                    id=uuid4(),
                    account_type=account_type,
                    owner_id=owner_id,
                    topic_kind=topic_kind,
                    chat_id=chat_id,
                    message_thread_id=None,
                    status="fallback",
                )
                self.topics[topic.id] = topic
        return tuple(self.topics.values())

    async def update_mapping(
        self,
        *,
        topic_id: UUID,
        chat_id: int,
        message_thread_id: int | None,
        status: str,
    ) -> TelegramTopicDTO | None:
        topic = self.topics.get(topic_id)
        if topic is None:
            return None
        updated = TelegramTopicDTO(
            id=topic.id,
            account_type=topic.account_type,
            owner_id=topic.owner_id,
            topic_kind=topic.topic_kind,
            chat_id=chat_id,
            message_thread_id=message_thread_id,
            status=status,
        )
        self.topics[topic_id] = updated
        return updated


@pytest.mark.asyncio
async def test_ensure_topics_creates_all_topic_kinds_as_fallback() -> None:
    repository = FakeTelegramTopicRepository()

    topics = await EnsureTelegramTopicsUseCase(repository).execute(
        EnsureTelegramTopicsCommand(
            account_type="customer",
            telegram_id=123,
            chat_id=123,
        ),
    )

    assert tuple(topic.topic_kind for topic in topics) == CUSTOMER_TOPIC_KINDS
    assert {topic.status for topic in topics} == {"fallback"}
    assert {topic.message_thread_id for topic in topics} == {None}


@pytest.mark.asyncio
async def test_ensure_topics_uses_performer_topic_kinds() -> None:
    repository = FakeTelegramTopicRepository()

    topics = await EnsureTelegramTopicsUseCase(repository).execute(
        EnsureTelegramTopicsCommand(
            account_type="performer",
            telegram_id=123,
            chat_id=123,
        ),
    )

    assert tuple(topic.topic_kind for topic in topics) == PERFORMER_TOPIC_KINDS


@pytest.mark.asyncio
async def test_ensure_topics_rejects_unknown_owner() -> None:
    repository = FakeTelegramTopicRepository()

    with pytest.raises(NotFoundError):
        await EnsureTelegramTopicsUseCase(repository).execute(
            EnsureTelegramTopicsCommand(
                account_type="customer",
                telegram_id=404,
                chat_id=123,
            ),
        )


@pytest.mark.asyncio
async def test_ensure_topics_rejects_bad_account_type() -> None:
    repository = FakeTelegramTopicRepository()

    with pytest.raises(ValidationError):
        await EnsureTelegramTopicsUseCase(repository).execute(
            EnsureTelegramTopicsCommand(
                account_type="admin",
                telegram_id=123,
                chat_id=123,
            ),
        )


@pytest.mark.asyncio
async def test_update_topic_mapping_accepts_active_thread() -> None:
    repository = FakeTelegramTopicRepository()
    topics = await repository.ensure_topics(
        account_type="customer",
        owner_id=repository.owner_id,
        chat_id=123,
        topic_kinds=CUSTOMER_TOPIC_KINDS,
    )

    topic = await UpdateTelegramTopicMappingUseCase(repository).execute(
        UpdateTelegramTopicMappingCommand(
            topic_id=topics[0].id,
            chat_id=123,
            message_thread_id=456,
            status="active",
        ),
    )

    assert topic.message_thread_id == 456
    assert topic.status == "active"

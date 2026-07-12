from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import utc_now
from backend.modules.customers.infrastructure import CustomerModel
from backend.modules.performers.infrastructure import PerformerModel
from backend.modules.telegram_topics.application.dto import TelegramTopicDTO
from backend.modules.telegram_topics.application.use_cases import TOPIC_KINDS
from backend.modules.telegram_topics.infrastructure.persistence.models import (
    TelegramTopicModel,
)


class SqlAlchemyTelegramTopicRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_owner_id(self, *, account_type: str, telegram_id: int) -> UUID | None:
        model_type = CustomerModel if account_type == "customer" else PerformerModel
        result = await self._session.execute(
            select(model_type.id).where(model_type.telegram_id == telegram_id),
        )
        return result.scalar_one_or_none()

    async def ensure_topics(
        self,
        *,
        account_type: str,
        owner_id: UUID,
        chat_id: int,
    ) -> tuple[TelegramTopicDTO, ...]:
        result = await self._session.execute(
            select(TelegramTopicModel).where(
                TelegramTopicModel.account_type == account_type,
                TelegramTopicModel.owner_id == owner_id,
            ),
        )
        existing = {topic.topic_kind: topic for topic in result.scalars()}
        for topic_kind in TOPIC_KINDS:
            topic = existing.get(topic_kind)
            if topic is None:
                topic = TelegramTopicModel(
                    account_type=account_type,
                    owner_id=owner_id,
                    topic_kind=topic_kind,
                    chat_id=chat_id,
                    message_thread_id=None,
                    status="fallback",
                )
                self._session.add(topic)
                existing[topic_kind] = topic
            else:
                topic.chat_id = chat_id
                topic.updated_at = utc_now()
        await self._session.flush()
        return tuple(_to_dto(existing[topic_kind]) for topic_kind in TOPIC_KINDS)

    async def update_mapping(
        self,
        *,
        topic_id: UUID,
        chat_id: int,
        message_thread_id: int | None,
        status: str,
    ) -> TelegramTopicDTO | None:
        topic = await self._session.get(TelegramTopicModel, topic_id)
        if topic is None:
            return None
        topic.chat_id = chat_id
        topic.message_thread_id = message_thread_id
        topic.status = status
        topic.updated_at = utc_now()
        await self._session.flush()
        return _to_dto(topic)


def _to_dto(topic: TelegramTopicModel) -> TelegramTopicDTO:
    return TelegramTopicDTO(
        id=topic.id,
        account_type=topic.account_type,
        owner_id=topic.owner_id,
        topic_kind=topic.topic_kind,
        chat_id=topic.chat_id,
        message_thread_id=topic.message_thread_id,
        status=topic.status,
    )


__all__ = ["SqlAlchemyTelegramTopicRepository"]

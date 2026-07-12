from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key
from backend.modules.telegram_topics.application import (
    EnsureTelegramTopicsCommand,
    EnsureTelegramTopicsUseCase,
    TelegramTopicDTO,
    UpdateTelegramTopicMappingCommand,
    UpdateTelegramTopicMappingUseCase,
)
from backend.modules.telegram_topics.infrastructure import (
    SqlAlchemyTelegramTopicRepository,
)

router = APIRouter(
    prefix="/api/telegram-topics",
    tags=["telegram-topics"],
    dependencies=[Depends(require_service_key)],
)


class EnsureTopicsRequest(BaseModel):
    chat_id: int


class UpdateTopicMappingRequest(BaseModel):
    chat_id: int
    message_thread_id: int | None = None
    status: str


class TelegramTopicResponse(BaseModel):
    id: str
    account_type: str
    owner_id: str
    topic_kind: str
    chat_id: int
    message_thread_id: int | None
    status: str


@router.post("/{account_type}/{telegram_id}/ensure")
async def ensure_topics(
    account_type: str,
    telegram_id: int,
    request: EnsureTopicsRequest,
    container: Annotated[Container, Depends(get_container)],
) -> list[TelegramTopicResponse]:
    async with container.session_factory() as session:
        topics = await EnsureTelegramTopicsUseCase(
            SqlAlchemyTelegramTopicRepository(session),
        ).execute(
            EnsureTelegramTopicsCommand(
                account_type=account_type,
                telegram_id=telegram_id,
                chat_id=request.chat_id,
            ),
        )
        await session.commit()
    return [_to_response(topic) for topic in topics]


@router.patch("/{topic_id}/mapping")
async def update_mapping(
    topic_id: UUID,
    request: UpdateTopicMappingRequest,
    container: Annotated[Container, Depends(get_container)],
) -> TelegramTopicResponse:
    async with container.session_factory() as session:
        topic = await UpdateTelegramTopicMappingUseCase(
            SqlAlchemyTelegramTopicRepository(session),
        ).execute(
            UpdateTelegramTopicMappingCommand(
                topic_id=topic_id,
                chat_id=request.chat_id,
                message_thread_id=request.message_thread_id,
                status=request.status,
            ),
        )
        await session.commit()
    return _to_response(topic)


def _to_response(topic: TelegramTopicDTO) -> TelegramTopicResponse:
    return TelegramTopicResponse(
        id=str(topic.id),
        account_type=topic.account_type,
        owner_id=str(topic.owner_id),
        topic_kind=topic.topic_kind,
        chat_id=topic.chat_id,
        message_thread_id=topic.message_thread_id,
        status=topic.status,
    )


__all__ = ["router"]

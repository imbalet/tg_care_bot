import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from redis.asyncio import Redis

from executor_bot.infrastructure.http import BackendClient, TelegramTopicDTO
from executor_bot.infrastructure.redis import executor_redis_keys

logger = logging.getLogger(__name__)

TOPIC_TITLES = {
    "work": "Заказы",
    "notifications": "Уведомления",
}


class TelegramTopicSetupService:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def ensure(
        self,
        *,
        bot: Bot,
        backend_client: BackendClient,
        telegram_id: int,
        chat_id: int,
    ) -> tuple[TelegramTopicDTO, ...]:
        topics = await backend_client.ensure_telegram_topics(
            telegram_id=telegram_id,
            chat_id=chat_id,
        )
        await self._hide_general_topic(bot=bot, chat_id=chat_id)
        updated = []
        for topic in topics:
            updated.append(
                await self._ensure_topic(
                    bot=bot,
                    backend_client=backend_client,
                    telegram_id=telegram_id,
                    chat_id=chat_id,
                    topic=topic,
                ),
            )
        return tuple(updated)

    async def _ensure_topic(
        self,
        *,
        bot: Bot,
        backend_client: BackendClient,
        telegram_id: int,
        chat_id: int,
        topic: TelegramTopicDTO,
    ) -> TelegramTopicDTO:
        if topic.message_thread_id is not None and topic.status == "active":
            await self._cache_topic(telegram_id, topic)
            return topic
        try:
            created = await bot.create_forum_topic(
                chat_id=chat_id,
                name=TOPIC_TITLES.get(topic.topic_kind, topic.topic_kind),
            )
            updated = await backend_client.update_telegram_topic_mapping(
                topic_id=topic.id,
                chat_id=chat_id,
                message_thread_id=created.message_thread_id,
                status="active",
            )
        except TelegramAPIError, ValueError:
            logger.warning("failed to create executor topic", exc_info=True)
            updated = await backend_client.update_telegram_topic_mapping(
                topic_id=topic.id,
                chat_id=chat_id,
                message_thread_id=None,
                status="fallback",
            )
        await self._cache_topic(telegram_id, updated)
        return updated

    async def _cache_topic(self, telegram_id: int, topic: TelegramTopicDTO) -> None:
        if topic.message_thread_id is None:
            await self._redis.set(
                executor_redis_keys.topic_thread_by_kind(
                    telegram_id,
                    topic.topic_kind,
                ),
                "",
            )
            return
        await self._redis.set(
            executor_redis_keys.topic_kind_by_thread(
                telegram_id,
                topic.message_thread_id,
            ),
            topic.topic_kind,
        )
        await self._redis.set(
            executor_redis_keys.topic_thread_by_kind(telegram_id, topic.topic_kind),
            topic.message_thread_id,
        )

    async def _hide_general_topic(self, *, bot: Bot, chat_id: int) -> None:
        try:
            await bot.hide_general_forum_topic(chat_id=chat_id)
        except TelegramAPIError:
            logger.warning("failed to hide general topic", exc_info=True)


__all__ = ["TOPIC_TITLES", "TelegramTopicSetupService"]

import logging

from customer_bot.application.dto import TelegramTopicDTO
from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import BackendPort, TopicCache
from customer_bot.application.ports.telegram import TelegramBotPort, TelegramPortError

logger = logging.getLogger(__name__)

TOPIC_TITLES = {
    "children": "Дети",
    "wards": "Подопечные",
    "pets": "Питомцы",
    "notifications": "Уведомления",
}


class TelegramTopicSetupService:
    def __init__(
        self,
        *,
        backend: BackendPort,
        topic_cache: TopicCache,
    ) -> None:
        self._backend = backend
        self._topic_cache = topic_cache

    async def ensure(
        self,
        *,
        bot: TelegramBotPort,
        telegram_id: int,
        chat_id: int,
    ) -> tuple[TelegramTopicDTO, ...]:
        topics = await self._backend.ensure_telegram_topics(
            telegram_id=telegram_id,
            chat_id=chat_id,
        )
        await self._hide_general_topic(bot=bot, chat_id=chat_id)
        updated = []
        for topic in topics:
            updated.append(
                await self._ensure_topic(
                    bot=bot,
                    telegram_id=telegram_id,
                    chat_id=chat_id,
                    topic=topic,
                ),
            )
        return tuple(updated)

    async def _ensure_topic(
        self,
        *,
        bot: TelegramBotPort,
        telegram_id: int,
        chat_id: int,
        topic: TelegramTopicDTO,
    ) -> TelegramTopicDTO:
        if topic.message_thread_id is not None and topic.status == "active":
            await self._cache_topic(telegram_id, topic)
            return topic
        try:
            message_thread_id = await bot.create_forum_topic(
                chat_id=chat_id,
                name=TOPIC_TITLES.get(topic.topic_kind, topic.topic_kind),
            )
            updated = await self._backend.update_telegram_topic_mapping(
                topic_id=topic.id,
                chat_id=chat_id,
                message_thread_id=message_thread_id,
                status="active",
            )
        except BackendClientError, TelegramPortError:
            logger.warning("failed to create customer topic", exc_info=True)
            updated = await self._backend.update_telegram_topic_mapping(
                topic_id=topic.id,
                chat_id=chat_id,
                message_thread_id=None,
                status="fallback",
            )
        await self._cache_topic(telegram_id, updated)
        return updated

    async def _cache_topic(self, telegram_id: int, topic: TelegramTopicDTO) -> None:
        await self._topic_cache.save_topic_thread(
            telegram_id=telegram_id,
            topic_kind=topic.topic_kind,
            message_thread_id=topic.message_thread_id,
        )

    async def _hide_general_topic(self, *, bot: TelegramBotPort, chat_id: int) -> None:
        try:
            await bot.hide_general_forum_topic(chat_id=chat_id)
        except TelegramPortError:
            logger.warning("failed to hide general topic", exc_info=True)

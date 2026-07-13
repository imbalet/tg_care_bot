from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup, Message
from redis.asyncio import Redis

from executor_bot.infrastructure.redis import executor_redis_keys


class MenuManager:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def topic_key(
        self,
        *,
        telegram_id: int,
        message_thread_id: int | None,
    ) -> str:
        if message_thread_id is None:
            return "general"
        key = executor_redis_keys.topic_kind_by_thread(telegram_id, message_thread_id)
        topic_kind = await self._redis.get(key)
        return topic_kind if isinstance(topic_kind, str) and topic_kind else "general"

    async def send_or_replace(
        self,
        *,
        bot: Bot,
        message: Message,
        telegram_id: int,
        topic_key: str,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
    ) -> Message:
        key = executor_redis_keys.menu_message(telegram_id, topic_key)
        current = await self._redis.get(key)
        if isinstance(current, str):
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=int(current),
                    text=text,
                    reply_markup=reply_markup,
                )
                return message
            except TelegramAPIError, ValueError:
                await self._redis.delete(key)

        sent = await message.answer(
            text,
            reply_markup=reply_markup,
            message_thread_id=message_thread_id,
        )
        await self._redis.set(key, sent.message_id)
        return sent


__all__ = ["MenuManager"]

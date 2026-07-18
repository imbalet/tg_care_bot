from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from redis.asyncio import Redis

from executor_bot.infrastructure.redis import executor_redis_keys


class MenuManager:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def update(
        self,
        *,
        bot: Bot,
        event: Message | CallbackQuery,
        telegram_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        create_new: bool = False,
    ) -> Message | None:
        message = event if isinstance(event, Message) else event.message
        if not isinstance(message, Message):
            if isinstance(event, CallbackQuery):
                await event.answer("Сообщение недоступно", show_alert=True)
            return None
        if isinstance(event, CallbackQuery):
            await event.answer()
        key = executor_redis_keys.menu_message(telegram_id)
        current = await self._redis.get(key)
        target_message_id = None
        if isinstance(current, str):
            try:
                target_message_id = int(current)
            except ValueError:
                await self._redis.delete(key)
        if (
            isinstance(event, CallbackQuery)
            and target_message_id is not None
            and message.message_id != target_message_id
        ):
            target_message_id = message.message_id
        if target_message_id is not None and not create_new:
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=target_message_id,
                    text=text,
                    reply_markup=reply_markup,
                )
                if isinstance(event, Message):
                    await _delete_message(message)
                return message
            except TelegramAPIError:
                await self._redis.delete(key)
        sent = await bot.send_message(
            chat_id=message.chat.id,
            text=text,
            reply_markup=reply_markup,
        )
        await self._redis.set(key, sent.message_id)
        if isinstance(event, Message) and event.message_id != sent.message_id:
            await _delete_message(event)
        return sent


async def _delete_message(message: Message) -> None:
    try:
        await message.delete()
    except TelegramAPIError:
        return


__all__ = ["MenuManager"]

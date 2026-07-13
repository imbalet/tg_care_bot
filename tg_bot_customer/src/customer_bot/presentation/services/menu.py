from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from customer_bot.application.ports import MenuMessageStore, TopicCache


class MenuManager:
    def __init__(
        self,
        *,
        message_store: MenuMessageStore,
        topic_cache: TopicCache,
    ) -> None:
        self._message_store = message_store
        self._topic_cache = topic_cache

    async def topic_key(
        self,
        *,
        telegram_id: int,
        message_thread_id: int | None,
    ) -> str:
        return await self._topic_cache.topic_kind_by_thread(
            telegram_id,
            message_thread_id,
        )

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
        await self.update(
            bot=bot,
            event=message,
            telegram_id=telegram_id,
            topic_key=topic_key,
            text=text,
            reply_markup=reply_markup,
            message_thread_id=message_thread_id,
        )
        return message

    async def update(
        self,
        *,
        bot: Bot,
        event: Message | CallbackQuery,
        telegram_id: int,
        topic_key: str,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        create_new: bool = False,
    ) -> Message | None:
        message = event if isinstance(event, Message) else event.message
        if not isinstance(message, Message):
            if isinstance(event, CallbackQuery):
                await event.answer("Сообщение недоступно", show_alert=True)
            return None

        if isinstance(event, CallbackQuery):
            await event.answer()

        target_message_id = await self._message_store.get(telegram_id, topic_key)
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
                    await _delete_message(event)
                return message
            except TelegramAPIError:
                await self._message_store.delete(telegram_id, topic_key)

        sent = await bot.send_message(
            chat_id=message.chat.id,
            text=text,
            reply_markup=reply_markup,
            message_thread_id=message_thread_id,
        )
        await self._message_store.set(telegram_id, topic_key, sent.message_id)
        if isinstance(event, Message) and event.message_id != sent.message_id:
            await _delete_message(event)
        return sent


async def _delete_message(message: Message) -> None:
    try:
        await message.delete()
    except TelegramAPIError:
        return

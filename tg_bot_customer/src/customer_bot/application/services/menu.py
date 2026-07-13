from aiogram.types import InlineKeyboardMarkup

from customer_bot.application.ports import MenuMessageStore, TopicCache
from customer_bot.application.ports.telegram import (
    TelegramBotPort,
    TelegramMenuEvent,
    TelegramPortError,
)


class MenuUpdateService:
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

    async def update(
        self,
        *,
        bot: TelegramBotPort,
        event: TelegramMenuEvent,
        telegram_id: int,
        topic_key: str,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        create_new: bool = False,
    ) -> None:
        if event.is_callback:
            await event.answer_callback()
        target_message_id = await self._message_store.get(telegram_id, topic_key)
        if (
            event.is_callback
            and target_message_id is not None
            and event.message_id != target_message_id
        ):
            target_message_id = event.message_id
        if target_message_id is not None and not create_new:
            try:
                await bot.edit_message_text(
                    chat_id=event.chat_id,
                    message_id=target_message_id,
                    text=text,
                    reply_markup=reply_markup,
                )
                await event.delete_if_user_message()
                return
            except TelegramPortError:
                await self._message_store.delete(telegram_id, topic_key)

        sent = await bot.send_message(
            chat_id=event.chat_id,
            text=text,
            reply_markup=reply_markup,
            message_thread_id=message_thread_id,
        )
        await self._message_store.set(telegram_id, topic_key, sent.message_id)
        await event.delete_if_user_message()

from aiogram import Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from customer_bot.application.services import MenuUpdateService
from customer_bot.presentation.adapters import AiogramBotAdapter, AiogramMenuEvent


class MenuManager:
    def __init__(self, service: MenuUpdateService) -> None:
        self._service = service

    async def topic_key(
        self,
        *,
        telegram_id: int,
        message_thread_id: int | None,
    ) -> str:
        return await self._service.topic_key(
            telegram_id=telegram_id,
            message_thread_id=message_thread_id,
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
        menu_event = AiogramMenuEvent(event)
        if menu_event.message is None:
            await menu_event.answer_unavailable()
            return None
        await self._service.update(
            bot=AiogramBotAdapter(bot),
            event=menu_event,
            telegram_id=telegram_id,
            topic_key=topic_key,
            text=text,
            reply_markup=reply_markup,
            message_thread_id=message_thread_id,
            create_new=create_new,
        )
        return menu_event.message

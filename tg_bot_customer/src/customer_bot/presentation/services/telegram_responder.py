from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from customer_bot.application.ports import ScreenMessageStore


class TelegramResponder:
    def __init__(
        self,
        *,
        message_store: ScreenMessageStore,
    ) -> None:
        self._message_store = message_store

    async def acknowledge(
        self,
        callback: CallbackQuery,
        text: str | None = None,
        *,
        show_alert: bool | None = None,
    ) -> None:
        await callback.answer(text, show_alert=show_alert)

    async def send_or_replace(
        self,
        *,
        bot: Bot,
        message: Message,
        telegram_id: int,
        screen_key: str,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        create_new: bool = False,
        delete_event_message: bool = True,
        store_message: bool = True,
    ) -> Message:
        sent = await self.update(
            bot=bot,
            event=message,
            telegram_id=telegram_id,
            screen_key=screen_key,
            text=text,
            reply_markup=reply_markup,
            create_new=create_new,
            delete_event_message=delete_event_message,
            store_message=store_message,
        )
        return sent or message

    async def update(
        self,
        *,
        bot: Bot,
        event: Message | CallbackQuery,
        telegram_id: int,
        screen_key: str,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        create_new: bool = False,
        delete_event_message: bool = True,
        store_message: bool = True,
    ) -> Message | None:
        message = event if isinstance(event, Message) else event.message
        if not isinstance(message, Message):
            if isinstance(event, CallbackQuery):
                await event.answer("Сообщение недоступно", show_alert=True)
            return None

        if isinstance(event, CallbackQuery):
            await event.answer()

        target_message_id = await self._message_store.get(telegram_id, screen_key)
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
                if delete_event_message and isinstance(event, Message):
                    await _delete_message(event)
                return message
            except TelegramAPIError:
                await self._message_store.delete(telegram_id, screen_key)

        sent = await bot.send_message(
            chat_id=message.chat.id,
            text=text,
            reply_markup=reply_markup,
        )
        if store_message:
            await self._message_store.set(telegram_id, screen_key, sent.message_id)
        if (
            delete_event_message
            and isinstance(event, Message)
            and event.message_id != sent.message_id
        ):
            await _delete_message(event)
        return sent


async def _delete_message(message: Message) -> None:
    try:
        await message.delete()
    except TelegramAPIError:
        return

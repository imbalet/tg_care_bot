import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, ReplyMarkupUnion

from customer_bot.application.ports import CurrentMessageStore

logger = logging.getLogger(__name__)


class TelegramResponder:
    def __init__(
        self,
        *,
        message_store: CurrentMessageStore,
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

    async def update(
        self,
        *,
        bot: Bot,
        event: Message | CallbackQuery,
        telegram_id: int,
        text: str,
        reply_markup: ReplyMarkupUnion | None = None,
        create_new: bool = False,
        delete_event_message: bool = False,
    ) -> Message | None:
        message = event if isinstance(event, Message) else event.message
        if not isinstance(message, Message):
            if isinstance(event, CallbackQuery):
                await event.answer("Сообщение недоступно", show_alert=True)
            logger.warning(
                "Telegram event has no message to update",
                extra={
                    "telegram_id": telegram_id,
                    "event_type": type(event).__name__,
                },
            )
            return None

        if isinstance(event, CallbackQuery):
            await event.answer()

        target_message_id = await self._message_store.get(telegram_id)
        if (
            isinstance(event, CallbackQuery)
            and target_message_id is not None
            and message.message_id != target_message_id
        ):
            target_message_id = message.message_id

        if (
            target_message_id is not None
            and not create_new
            and (reply_markup is None or isinstance(reply_markup, InlineKeyboardMarkup))
        ):
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=target_message_id,
                    text=text,
                    reply_markup=reply_markup,
                )
                await self._message_store.set(telegram_id, target_message_id)
                if delete_event_message and isinstance(event, Message):
                    await _delete_message(event)
                return message
            except TelegramAPIError as exc:
                logger.warning(
                    "Telegram message edit failed",
                    extra={
                        "telegram_id": telegram_id,
                        "chat_id": message.chat.id,
                        "message_id": target_message_id,
                        "exception_type": type(exc).__name__,
                    },
                )
                await self._message_store.delete(telegram_id)

        sent = await bot.send_message(
            chat_id=message.chat.id,
            text=text,
            reply_markup=reply_markup,
        )
        await self._message_store.set(telegram_id, sent.message_id)
        if (
            delete_event_message
            and isinstance(event, Message)
            and event.message_id != sent.message_id
        ):
            await _delete_message(event)
        return sent

    async def send_notice(
        self,
        *,
        bot: Bot,
        event: Message | CallbackQuery,
        telegram_id: int,
        text: str,
        reply_markup: ReplyMarkupUnion | None = None,
    ) -> Message | None:
        return await self._send(
            bot=bot,
            event=event,
            telegram_id=telegram_id,
            text=text,
            reply_markup=reply_markup,
            store_message=False,
        )

    async def send_contact(
        self,
        *,
        bot: Bot,
        event: Message | CallbackQuery,
        phone_number: str,
        first_name: str,
    ) -> Message | None:
        message = event if isinstance(event, Message) else event.message
        if not isinstance(message, Message):
            return None
        return await bot.send_contact(
            chat_id=message.chat.id,
            phone_number=phone_number,
            first_name=first_name,
        )

    async def delete_clicked_message(self, callback: CallbackQuery) -> None:
        if isinstance(callback.message, Message):
            await _delete_message(callback.message)
        await callback.answer()

    async def _send(
        self,
        *,
        bot: Bot,
        event: Message | CallbackQuery,
        telegram_id: int,
        text: str,
        reply_markup: ReplyMarkupUnion | None,
        store_message: bool,
    ) -> Message | None:
        message = event if isinstance(event, Message) else event.message
        if not isinstance(message, Message):
            if isinstance(event, CallbackQuery):
                await event.answer("Сообщение недоступно", show_alert=True)
            logger.warning(
                "Telegram event has no message to answer",
                extra={
                    "telegram_id": telegram_id,
                    "event_type": type(event).__name__,
                },
            )
            return None

        if isinstance(event, CallbackQuery):
            await event.answer()

        sent = await bot.send_message(
            chat_id=message.chat.id,
            text=text,
            reply_markup=reply_markup,
        )
        if store_message:
            await self._message_store.set(telegram_id, sent.message_id)
        return sent


async def _delete_message(message: Message) -> None:
    try:
        await message.delete()
    except TelegramAPIError as exc:
        logger.warning(
            "Telegram message delete failed",
            extra={
                "chat_id": message.chat.id,
                "message_id": message.message_id,
                "exception_type": type(exc).__name__,
            },
        )
        return

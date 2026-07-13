from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from customer_bot.application.ports.telegram import SentMessage, TelegramPortError


class AiogramBotAdapter:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def edit_message_text(
        self,
        *,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None,
    ) -> None:
        try:
            await self._bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
            )
        except TelegramAPIError as exc:
            raise TelegramPortError("Failed to edit Telegram message") from exc

    async def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None,
        message_thread_id: int | None,
    ) -> SentMessage:
        try:
            message = await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                message_thread_id=message_thread_id,
            )
        except TelegramAPIError as exc:
            raise TelegramPortError("Failed to send Telegram message") from exc
        return SentMessage(message_id=message.message_id)

    async def create_forum_topic(
        self,
        *,
        chat_id: int,
        name: str,
    ) -> int:
        try:
            topic = await self._bot.create_forum_topic(chat_id=chat_id, name=name)
        except TelegramAPIError as exc:
            raise TelegramPortError("Failed to create Telegram forum topic") from exc
        return topic.message_thread_id

    async def hide_general_forum_topic(self, *, chat_id: int) -> None:
        try:
            await self._bot.hide_general_forum_topic(chat_id=chat_id)
        except TelegramAPIError as exc:
            raise TelegramPortError("Failed to hide Telegram general topic") from exc


class AiogramMenuEvent:
    def __init__(self, event: Message | CallbackQuery) -> None:
        self._event = event

    @property
    def message(self) -> Message | None:
        if isinstance(self._event, Message):
            return self._event
        return self._event.message if isinstance(self._event.message, Message) else None

    @property
    def chat_id(self) -> int:
        message = self.message
        if message is None:
            raise TelegramPortError("Telegram message is unavailable")
        return message.chat.id

    @property
    def message_id(self) -> int:
        message = self.message
        if message is None:
            raise TelegramPortError("Telegram message is unavailable")
        return message.message_id

    @property
    def is_callback(self) -> bool:
        return isinstance(self._event, CallbackQuery)

    @property
    def is_user_message(self) -> bool:
        return isinstance(self._event, Message)

    async def answer_callback(self) -> None:
        if isinstance(self._event, CallbackQuery):
            await self._event.answer()

    async def answer_unavailable(self) -> None:
        if isinstance(self._event, CallbackQuery):
            await self._event.answer("Сообщение недоступно", show_alert=True)

    async def delete_if_user_message(self) -> None:
        if not isinstance(self._event, Message):
            return
        try:
            await self._event.delete()
        except TelegramAPIError:
            return

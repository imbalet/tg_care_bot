from dataclasses import dataclass
from typing import Protocol

from aiogram.types import InlineKeyboardMarkup


class TelegramPortError(Exception):
    """Telegram operation failed."""


@dataclass(frozen=True)
class SentMessage:
    message_id: int


class TelegramMenuEvent(Protocol):
    @property
    def chat_id(self) -> int: ...

    @property
    def message_id(self) -> int: ...

    @property
    def is_callback(self) -> bool: ...

    @property
    def is_user_message(self) -> bool: ...

    async def answer_callback(self) -> None: ...

    async def answer_unavailable(self) -> None: ...

    async def delete_if_user_message(self) -> None: ...


class TelegramBotPort(Protocol):
    async def edit_message_text(
        self,
        *,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None,
    ) -> None: ...

    async def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None,
        message_thread_id: int | None,
    ) -> SentMessage: ...

    async def create_forum_topic(
        self,
        *,
        chat_id: int,
        name: str,
    ) -> int: ...

    async def hide_general_forum_topic(self, *, chat_id: int) -> None: ...

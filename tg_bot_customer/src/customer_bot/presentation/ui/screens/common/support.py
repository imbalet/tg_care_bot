from html import escape
from typing import Protocol
from urllib.parse import urlparse

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    SupportRequestOpenCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _View(Protocol):
    @property
    def label(self) -> str: ...

    @property
    def telegram_url(self) -> str | None: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return f"<b>{escape(self.data.label)}</b>\n\nОткройте поддержку кнопкой ниже."

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        if _is_valid_telegram_url(self.data.telegram_url):
            keyboard.url_button(self.data.label, self.data.telegram_url)
        keyboard.button("Написать в поддержку", SupportRequestOpenCallback())
        keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback())
        return keyboard.as_markup()


def _is_valid_telegram_url(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

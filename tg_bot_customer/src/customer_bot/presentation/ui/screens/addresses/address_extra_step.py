from html import escape
from typing import Protocol

from customer_bot.presentation.callbacks import (
    AddressSkipCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _View(Protocol):
    @property
    def field_name(self) -> str: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return (
            f"<b>{escape(self.data.field_name)}</b>\n\nВведите значение или пропустите."
        )

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button(MsgKey.SKIP, AddressSkipCallback())
            .as_markup()
        )

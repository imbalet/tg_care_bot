from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderServiceCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _Item(Protocol):
    @property
    def id(self) -> object: ...

    @property
    def name(self) -> str: ...


class _View(Protocol):
    @property
    def services(self) -> Sequence[_Item]: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return "<b>Новый заказ</b>\n\nВыберите услугу."

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        for item in self.data.services:
            keyboard.button(
                item.name,
                OrderServiceCallback(service_id=UUID(str(item.id))),
            )
        return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()

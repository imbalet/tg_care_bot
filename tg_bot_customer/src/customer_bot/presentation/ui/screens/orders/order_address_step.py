from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderAddressCallback,
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
    def address_text(self) -> str: ...


type _View = Sequence[_Item]


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return "<b>Адрес</b>\n\nВыберите адрес заказа."

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        for item in self.data:
            keyboard.button(
                item.address_text,
                OrderAddressCallback(address_id=UUID(str(item.id))),
            )
        return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()

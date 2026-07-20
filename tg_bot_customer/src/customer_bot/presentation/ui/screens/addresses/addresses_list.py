from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    AddressAddCallback,
    AddressSelectCallback,
    MainMenuCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _AddressItem(Protocol):
    @property
    def id(self) -> object: ...

    @property
    def address_text(self) -> str: ...


class _View(Protocol):
    @property
    def count(self) -> int: ...

    @property
    def items(self) -> Sequence[_AddressItem]: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        if self.data.count == 0:
            return "<b>Адреса</b>\n\nДобавьте адрес до создания заказа."
        return "<b>Адреса</b>\n\nВыберите адрес или добавьте новый."

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory().button(
            MsgKey.ADD_ADDRESS, AddressAddCallback()
        )
        for index, item in enumerate(self.data.items):
            address_text = getattr(item, "address_text", f"#{index + 1}")
            keyboard.button(
                str(address_text),
                AddressSelectCallback(address_id=UUID(str(item.id))),
            )
        return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()

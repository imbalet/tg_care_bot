from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    AddressDeleteConfirmCallback,
    AddressesOpenCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _View(Protocol):
    @property
    def id(self) -> str: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return (
            "<b>Удалить адрес?</b>\n\n"
            "Адрес будет скрыт из активного списка. Старые заказы сохранят свою "
            "историю."
        )

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button(
                MsgKey.DELETE,
                AddressDeleteConfirmCallback(address_id=UUID(str(self.data.id))),
            )
            .button(MsgKey.BACK_TO_LIST, AddressesOpenCallback())
            .as_markup()
        )

from html import escape
from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    AddressDeleteCallback,
    AddressEditCallback,
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

    @property
    def address_text(self) -> str: ...

    @property
    def entrance(self) -> str: ...

    @property
    def floor(self) -> str: ...

    @property
    def apartment(self) -> str: ...

    @property
    def comment(self) -> str: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        address_text = escape(self.data.address_text)
        entrance = escape(self.data.entrance)
        floor = escape(self.data.floor)
        apartment = escape(self.data.apartment)
        comment = escape(self.data.comment)
        lines = ["<b>Адрес</b>", "", address_text]
        if isinstance(entrance, str):
            lines.append(f"Подъезд: {entrance}")
        if isinstance(floor, str):
            lines.append(f"Этаж: {floor}")
        if isinstance(apartment, str):
            lines.append(f"Квартира: {apartment}")
        if isinstance(comment, str):
            lines.append(f"Комментарий: {comment}")
        return "\n".join(lines)

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button(
                "Редактировать",
                AddressEditCallback(address_id=UUID(str(self.data.id))),
            )
            .button(
                MsgKey.DELETE,
                AddressDeleteCallback(address_id=UUID(str(self.data.id))),
            )
            .button(MsgKey.BACK_TO_LIST, AddressesOpenCallback())
            .as_markup()
        )

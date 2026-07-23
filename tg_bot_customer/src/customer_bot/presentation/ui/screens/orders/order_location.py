from html import escape
from typing import Protocol

from customer_bot.application.dto import FullAddressSnapshotDTO
from customer_bot.presentation.callbacks import MainMenuCallback, OrdersListCallback
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import BaseScreen, Markup


class _View(Protocol):
    @property
    def city_name(self) -> str: ...

    @property
    def district_name(self) -> str | None: ...

    @property
    def address(self) -> FullAddressSnapshotDTO | None: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        lines = ["<b>Место оказания услуги</b>", ""]
        lines.append(f"Город: {escape(self.data.city_name)}")
        if self.data.district_name:
            lines.append(f"Район: {escape(self.data.district_name)}")
        address = self.data.address
        if address is not None:
            lines.extend(
                (
                    "",
                    f"Адрес: {escape(address.address_text)}",
                ),
            )
            for label, value in (
                ("Подъезд", address.entrance),
                ("Этаж", address.floor),
                ("Квартира", address.apartment),
                ("Комментарий", address.comment),
            ):
                if value:
                    lines.append(f"{label}: {escape(value)}")
        else:
            lines.extend(("", "Точный адрес пока недоступен."))
        return "\n".join(lines)

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button("К заказам", OrdersListCallback())
            .button("Главное меню", MainMenuCallback())
            .as_markup()
        )

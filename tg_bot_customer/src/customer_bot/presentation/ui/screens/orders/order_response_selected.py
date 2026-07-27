from html import escape
from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    PaymentRefreshCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.orders.status_labels import order_status_label
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _View(Protocol):
    @property
    def order_status(self) -> str: ...

    @property
    def id(self) -> UUID: ...

    @property
    def payment_confirmation_url(self) -> str | None: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        lines = [
            "<b>Исполнитель выбран</b>",
            "",
            f"Статус заказа: {order_status_label(self.data.order_status)}",
        ]
        if self.data.payment_confirmation_url:
            lines.extend(("", f"Оплата: {escape(self.data.payment_confirmation_url)}"))
        return "\n".join(lines)

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        if self.data.id is not None:
            keyboard.button(
                "Обновить статус оплаты",
                PaymentRefreshCallback(order_id=self.data.id),
            )
        return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()

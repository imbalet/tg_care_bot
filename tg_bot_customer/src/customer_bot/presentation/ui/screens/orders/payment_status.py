from datetime import datetime
from html import escape
from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    PaymentRefreshCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _View(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def order_status(self) -> str: ...

    @property
    def payment_status(self) -> str: ...

    @property
    def confirmation_url(self) -> str: ...

    @property
    def expires_at(self) -> datetime: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        order_status = escape(str(self.data.order_status))
        payment_status = self.data.payment_status
        confirmation_url = self.data.confirmation_url
        expires_at = self.data.expires_at
        lines = [
            "<b>Статус оплаты</b>",
            "",
            f"Статус заказа: {order_status}",
        ]
        if payment_status is not None:
            lines.append(f"Статус платежа: {escape(str(payment_status))}")
        if expires_at is not None:
            lines.append(f"Оплатить до: {escape(str(expires_at))}")
        if confirmation_url:
            lines.extend(("", f"Оплата: {escape(str(confirmation_url))}"))
        return "\n".join(lines)

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        if self.data.id is not None:
            keyboard.button(
                "Обновить статус оплаты",
                PaymentRefreshCallback(order_id=self.data.id),
            )
        return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()

from datetime import datetime
from html import escape
from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    PaymentRefreshCallback,
    PaymentRetryCallback,
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
    def payment_status(self) -> str | None: ...

    @property
    def confirmation_url(self) -> str | None: ...

    @property
    def expires_at(self) -> datetime | None: ...

    @property
    def failure_code(self) -> str | None: ...

    @property
    def attempts_used(self) -> int: ...

    @property
    def max_attempts(self) -> int: ...

    @property
    def retry_available(self) -> bool: ...


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
        if self.data.failure_code:
            lines.append("Платеж не выполнен. Можно попробовать оплатить снова.")
        lines.append(
            f"Попытки оплаты: {self.data.attempts_used} из {self.data.max_attempts}"
        )
        if expires_at is not None:
            lines.append(f"Оплатить до: {escape(str(expires_at))}")
        if confirmation_url:
            lines.extend(("", f"Оплата: {escape(str(confirmation_url))}"))
        return "\n".join(lines)

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        if self.data.id is not None:
            if self.data.retry_available:
                keyboard.button(
                    "Повторить оплату",
                    PaymentRetryCallback(order_id=self.data.id),
                )
            keyboard.button(
                "Обновить статус оплаты",
                PaymentRefreshCallback(order_id=self.data.id),
            )
        return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()

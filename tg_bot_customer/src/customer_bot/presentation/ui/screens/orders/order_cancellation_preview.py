from decimal import Decimal
from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    OrderCancelConfirmCallback,
    OrdersListCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import BaseScreen, Markup


class _View(Protocol):
    @property
    def order_id(self) -> UUID: ...

    @property
    def refund_outcome(self) -> str: ...

    @property
    def refund_amount(self) -> Decimal: ...

    @property
    def can_cancel(self) -> bool: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        if not self.data.can_cancel:
            return "<b>Отмена недоступна</b>\n\nЗаказ уже нельзя отменить."
        outcome = {
            "full": "Полный возврат",
            "partial": "Частичный возврат",
            "none": "Автоматического возврата нет",
        }.get(self.data.refund_outcome, "Финансовый результат уточняется")
        return (
            "<b>Отмена заказа</b>\n\n"
            f"Результат: {outcome}\n"
            f"Сумма возврата: {self.data.refund_amount} ₽\n\n"
            "Подтвердить отмену?"
        )

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        if self.data.can_cancel:
            keyboard.button(
                "Подтвердить отмену",
                OrderCancelConfirmCallback(order_id=self.data.order_id),
            )
        return keyboard.button("Назад", OrdersListCallback()).as_markup()

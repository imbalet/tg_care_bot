from html import escape
from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderResponsesOpenCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.orders.status_labels import (
    matching_mode_label,
    order_status_label,
)
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _View(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def service_name(self) -> str: ...

    @property
    def status(self) -> str: ...

    @property
    def matching_mode(self) -> str | None: ...

    @property
    def total_amount(self) -> object: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        mode = self.data.matching_mode or "pool"

        return "\n".join(
            (
                "<b>Заказ опубликован</b>",
                "",
                f"ID: {escape(str(self.data.id))}",
                f"Услуга: {escape(self.data.service_name)}",
                f"Статус: {order_status_label(self.data.status)}",
                f"Подбор: {matching_mode_label(mode)}",
                f"Итого: {escape(str(self.data.total_amount))}",
            ),
        )

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        order_id = self.data.id
        if self.data.matching_mode == "pool" and order_id is not None:
            keyboard.button(
                "Отклики",
                OrderResponsesOpenCallback(order_id=order_id),
            )
        return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()

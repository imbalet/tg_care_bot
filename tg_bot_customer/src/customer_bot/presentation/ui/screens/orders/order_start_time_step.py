from html import escape
from typing import Protocol

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderStartManualCallback,
    OrderStartTimeCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey

ORDER_START_TIME_VALUES = (
    "09:00",
    "10:00",
    "12:00",
    "14:00",
    "16:00",
    "18:00",
    "20:00",
)


def _order_start_time_callback_value(value: str) -> str:
    return value.replace(":", "")


class _View(Protocol):
    @property
    def date_label(self) -> str: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return (
            "<b>Время начала</b>\n\n"
            f"Дата: {escape(self.data.date_label)}.\n"
            "Выберите время или введите вручную."
        )

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory(row_width=3)
        for value in ORDER_START_TIME_VALUES:
            keyboard.button(
                value,
                OrderStartTimeCallback(value=_order_start_time_callback_value(value)),
            )
        return (
            keyboard.button(
                "Ввести дату и время вручную",
                OrderStartManualCallback(mode="datetime"),
            )
            .button(MsgKey.MAIN_MENU, MainMenuCallback())
            .as_markup()
        )

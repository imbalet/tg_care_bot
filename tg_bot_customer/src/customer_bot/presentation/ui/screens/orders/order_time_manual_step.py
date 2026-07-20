from html import escape
from typing import Protocol

from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
)


class _View(Protocol):
    @property
    def date_label(self) -> str: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return (
            "<b>Время начала</b>\n\n"
            f"Дата: {escape(self.data.date_label)}.\nВведите время в формате ЧЧ:ММ."
        )

from typing import Protocol

from customer_bot.presentation.ui.screens.common._keyboard import fallback_keyboard
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)


class _View(Protocol):
    @property
    def index(self) -> int: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return "Этот объект ухода нельзя удалить: он используется в активном заказе."

    def _build_keyboard(self) -> Markup:
        return fallback_keyboard()

from typing import Protocol

from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)


class _View(Protocol):
    @property
    def index(self) -> int: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        # TODO: нормальный текст
        return "Удаление заблокировано"

    def _build_keyboard(self) -> Markup:
        # TODO: клавиатура
        return None

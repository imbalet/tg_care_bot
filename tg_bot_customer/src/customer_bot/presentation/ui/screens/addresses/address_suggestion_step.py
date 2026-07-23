from collections.abc import Sequence
from typing import Protocol

from customer_bot.presentation.callbacks import (
    AddressSuggestionCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)


class _Adress(Protocol):
    @property
    def value(self) -> str: ...


type _View = Sequence[_Adress]


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        lines = ["<b>Подсказки адреса</b>", "", "Выберите подходящий вариант:"]
        lines.extend(
            f"{index}. {suggestion.value}"
            for index, suggestion in enumerate(self.data, start=1)
        )
        return "\n".join(lines)

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        for index, _suggestion in enumerate(self.data):
            keyboard.button(
                f"№{index + 1}",
                AddressSuggestionCallback(index=index),
            )
        return keyboard.as_markup()

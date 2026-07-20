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
        # TODO: писать адреса тут а не в кнопках
        return "<b>Подсказки адреса</b>\n\nВыберите подходящий вариант."

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        for index, suggestion in enumerate(self.data):
            keyboard.button(
                suggestion.value,
                AddressSuggestionCallback(index=index),
            )
        return keyboard.as_markup()

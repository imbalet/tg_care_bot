from collections.abc import Sequence
from typing import Protocol

from customer_bot.presentation.callbacks import (
    RegistrationCityCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import BaseScreen, Markup


class _City(Protocol):
    @property
    def name(self) -> str: ...


type _View = Sequence[_City]


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return "<b>Город</b>\n\nВыберите город, где будете создавать заказы."

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()

        for index, city in enumerate(self.data):
            keyboard.button(city.name, RegistrationCityCallback(index=index))
        return keyboard.as_markup()

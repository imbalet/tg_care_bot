from customer_bot.presentation.callbacks import MainMenuCallback
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "Введите дату и время в формате ГГГГ-ММ-ДД ЧЧ:ММ."

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button("Главное меню", MainMenuCallback())
            .as_markup()
        )

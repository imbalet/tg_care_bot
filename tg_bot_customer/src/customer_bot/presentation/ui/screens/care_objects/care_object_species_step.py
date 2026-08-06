from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "<b>Вид питомца</b>\n\nВведите вид: кошка, собака или другой."

    def _build_keyboard(self) -> Markup:
        return InlineKeyboardFactory().as_markup()

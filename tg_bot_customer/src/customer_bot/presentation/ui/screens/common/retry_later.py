from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)

from ._keyboard import fallback_keyboard


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "⚠️ <b>Сервис временно недоступен</b>\n\nПопробуйте еще раз чуть позже."

    def _build_keyboard(self) -> Markup:
        return fallback_keyboard(include_main_menu=True)

from customer_bot.presentation.ui.screens.common._keyboard import fallback_keyboard
from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "Не удалось сохранить адрес. Проверьте данные и попробуйте снова."

    def _build_keyboard(self) -> Markup:
        return fallback_keyboard()

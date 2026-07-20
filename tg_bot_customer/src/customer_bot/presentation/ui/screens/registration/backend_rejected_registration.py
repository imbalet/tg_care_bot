from customer_bot.presentation.ui.screens.common._keyboard import fallback_keyboard
from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return (
            "⚠️ <b>Данные не приняты</b>\n\n"
            "Проверьте регистрацию и начните заново командой /start."
        )

    def _build_keyboard(self) -> Markup:
        return fallback_keyboard()

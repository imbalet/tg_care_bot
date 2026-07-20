from customer_bot.presentation.ui.screens.common._keyboard import fallback_keyboard
from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return (
            "⚠️ <b>Не удалось продолжить регистрацию</b>\n\n"
            "Попробуйте открыть бот заново командой /start."
        )

    def _build_keyboard(self) -> Markup:
        return fallback_keyboard(include_main_menu=True)

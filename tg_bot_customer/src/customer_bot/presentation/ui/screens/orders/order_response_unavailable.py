from customer_bot.presentation.ui.screens.common._keyboard import fallback_keyboard
from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return (
            "<b>Отклик недоступен</b>\n\n"
            "Он уже обработан, устарел или заказ изменил состояние."
        )

    def _build_keyboard(self) -> Markup:
        return fallback_keyboard()

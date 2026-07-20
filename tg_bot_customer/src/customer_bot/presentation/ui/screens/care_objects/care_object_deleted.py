from customer_bot.presentation.ui.screens.common._keyboard import fallback_keyboard
from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)

CARE_OBJECT_LIST_LABELS = {
    "child": "Мои дети",
    "ward": "Мои подопечные",
    "pet": "Мои питомцы",
}


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "Карточка удалена из активного списка."

    def _build_keyboard(self) -> Markup:
        return fallback_keyboard()

from customer_bot.presentation.callbacks import (
    CareObjectSizeCallback,
    CareObjectSkipCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey

CARE_OBJECT_SIZE_LABELS = {
    "small": "Маленький",
    "medium": "Средний",
    "large": "Крупный",
    "unknown": "Не указано",
}


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "<b>Размер питомца</b>\n\nВыберите размер."

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        for value, label in CARE_OBJECT_SIZE_LABELS.items():
            keyboard.button(label, CareObjectSizeCallback(size=value))
        keyboard.button(MsgKey.SKIP, CareObjectSkipCallback())
        return keyboard.as_markup()

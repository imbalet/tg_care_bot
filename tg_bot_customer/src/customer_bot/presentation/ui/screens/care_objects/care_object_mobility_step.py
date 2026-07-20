from customer_bot.presentation.callbacks import (
    CareObjectMobilityCallback,
)
from customer_bot.presentation.types import YesNoValue
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "<b>Помощь с передвижением</b>\n\nНужна ли помощь?"

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button("Нужна помощь", CareObjectMobilityCallback(value=YesNoValue.YES))
            .button("Не нужна", CareObjectMobilityCallback(value=YesNoValue.NO))
            .as_markup()
        )

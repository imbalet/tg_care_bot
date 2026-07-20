from customer_bot.presentation.callbacks import (
    CareObjectSkipCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return (
            "<b>Комментарий</b>\n\n"
            "Опишите режим или поведение. Не указывайте диагнозы, лекарства, "
            "медицинские документы и другие медицинские сведения."
        )

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button(MsgKey.SKIP, CareObjectSkipCallback())
            .as_markup()
        )

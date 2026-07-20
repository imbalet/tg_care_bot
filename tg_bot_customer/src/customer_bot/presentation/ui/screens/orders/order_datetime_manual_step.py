from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "<b>Дата и время</b>\n\nВведите начало в формате ГГГГ-ММ-ДД ЧЧ:ММ."

    def _build_keyboard(self) -> Markup:
        return None

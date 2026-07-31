from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return (
            "<b>Дата и время</b>\n\n"
            "Выберите дату в календаре или введите дату и время вручную."
        )

    def _build_keyboard(self) -> Markup:
        # календарь
        return None

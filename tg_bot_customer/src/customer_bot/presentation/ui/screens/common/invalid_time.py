from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "Введите время в формате ЧЧ:ММ."

    # TODO: клавиатура

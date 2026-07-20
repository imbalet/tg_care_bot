from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "Введите дату и время в формате ГГГГ-ММ-ДД ЧЧ:ММ."

    # TODO: клавиатура

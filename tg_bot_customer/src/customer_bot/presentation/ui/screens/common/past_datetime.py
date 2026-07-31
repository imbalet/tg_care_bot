from customer_bot.presentation.ui.screens.screen import BaseScreenNoView


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return (
            "Время уже прошло. Выберите другое.\n\n"
            "Введите начало в формате ДД.ММ.ГГГГ ЧЧ:ММ."
        )

from customer_bot.presentation.ui.screens.screen import BaseScreen

type _View = bool


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        unit = "суток" if self.data else "часов"
        return f"Введите положительное целое количество {unit}."

    # TODO: клавиатура

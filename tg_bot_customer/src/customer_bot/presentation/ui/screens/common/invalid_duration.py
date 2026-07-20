from customer_bot.presentation.callbacks import MainMenuCallback
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import BaseScreen, Markup

type _View = str


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        unit = {"days": "суток", "hours": "часов", "minutes": "минут"}.get(
            self.data,
            "минут",
        )
        return f"Введите положительное целое количество {unit}."

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button("Главное меню", MainMenuCallback())
            .as_markup()
        )

from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "Адрес сохранен."

    def _build_keyboard(self) -> Markup:
        # TODO: клавиатура
        return super()._build_keyboard()

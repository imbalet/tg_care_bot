from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        # TODO: нормальный текст
        return "Ошибка"

    def _build_keyboard(self) -> Markup:
        # TODO: клавиатура
        return None

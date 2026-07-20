from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return (
            "⚠️ <b>Данные не приняты</b>\n\n"
            "Проверьте регистрацию и начните заново командой /start."
        )

    # TODO: клавиатура

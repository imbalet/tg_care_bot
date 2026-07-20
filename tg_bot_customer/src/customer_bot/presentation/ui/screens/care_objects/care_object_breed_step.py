from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "<b>Порода</b>\n\nВведите породу или пропустите шаг."

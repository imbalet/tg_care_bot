from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "<b>Адрес</b>\n\nВведите улицу, дом или полный адрес."

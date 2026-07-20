from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "<b>Вид питомца</b>\n\nВведите вид: кошка, собака или другой."

from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "<b>Новый заказ</b>\n\nСейчас нет активных услуг для заказа."

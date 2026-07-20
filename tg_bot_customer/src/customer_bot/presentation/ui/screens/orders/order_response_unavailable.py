from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return (
            "<b>Отклик недоступен</b>\n\n"
            "Он уже обработан, устарел или заказ изменил состояние."
        )

    # TODO: клавиатура

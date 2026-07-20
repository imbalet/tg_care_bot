from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return (
            "<b>Не понял сообщение</b>\n\n"
            "Откройте главное меню или помощь. Если вы заполняете форму, используйте "
            "кнопки и подсказки последнего сообщения."
        )

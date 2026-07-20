from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    SupportOpenCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return (
            "<b>Действие устарело или уже недоступно</b>\n\n"
            "Откройте главное меню или обратитесь в поддержку."
        )

    def _build_keyboard(self) -> Markup:
        # TODO: unify keyboard
        return (
            InlineKeyboardFactory()
            .button(MsgKey.MAIN_MENU, MainMenuCallback())
            .button("Поддержка", SupportOpenCallback())
            .as_markup()
        )

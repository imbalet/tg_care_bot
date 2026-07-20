from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderAddAddressCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "<b>Новый заказ</b>\n\nДобавьте адрес в разделе «Адреса»."

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button(MsgKey.ADD_ADDRESS, OrderAddAddressCallback())
            .button(MsgKey.MAIN_MENU, MainMenuCallback())
            .as_markup()
        )

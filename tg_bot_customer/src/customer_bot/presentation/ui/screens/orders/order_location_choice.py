from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderLocationChoiceCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import BaseScreen, Markup
from customer_bot.presentation.ui.texts.labels import MsgKey


class Screen(BaseScreen[None]):
    def _build_text(self) -> str:
        return "<b>Место оказания</b>\n\nГде будет находиться питомец во время заказа?"

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        keyboard.button(
            "У заказчика",
            OrderLocationChoiceCallback(source="customer_address"),
        )
        keyboard.button(
            "У исполнителя",
            OrderLocationChoiceCallback(source="performer_address"),
        )
        return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()

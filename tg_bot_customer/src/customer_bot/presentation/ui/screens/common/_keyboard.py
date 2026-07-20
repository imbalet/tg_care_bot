from aiogram.types import (
    InlineKeyboardMarkup,
)

from customer_bot.presentation.callbacks import HelpCallback, MainMenuCallback
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.texts.labels import MsgKey


def fallback_keyboard(*, include_main_menu: bool = True) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    if include_main_menu:
        keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback())
    return keyboard.button(MsgKey.HELP, HelpCallback()).as_markup()

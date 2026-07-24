from aiogram.types import (
    InlineKeyboardMarkup,
)

from customer_bot.presentation.callbacks import (
    HelpCallback,
    MainMenuCallback,
    SupportOpenCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.texts.labels import MsgKey


def fallback_keyboard(
    *, include_main_menu: bool = True, legal_documents: tuple[object, ...] = ()
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    if include_main_menu:
        keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback())
    for index, document in enumerate(legal_documents, start=1):
        url = str(getattr(document, "content_url", ""))
        if url.startswith(("https://", "http://")):
            keyboard.url_button(f"Документ {index}", url)
    return (
        keyboard.button(MsgKey.HELP, HelpCallback())
        .button("Связаться с поддержкой", SupportOpenCallback())
        .as_markup()
    )

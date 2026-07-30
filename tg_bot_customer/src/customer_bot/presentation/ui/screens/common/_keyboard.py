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
    *,
    include_main_menu: bool = True,
    include_help: bool = True,
    include_support: bool = True,
    support_label: str = "Поддержка",
    support_url: str | None = None,
    legal_documents: tuple[object, ...] = (),
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    if include_main_menu:
        keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback())
    for index, document in enumerate(legal_documents, start=1):
        url = str(getattr(document, "content_url", ""))
        if url.startswith(("https://", "http://")):
            keyboard.url_button(f"Документ {index}", url)
    if isinstance(support_url, str) and _is_valid_support_url(support_url):
        keyboard.url_button(support_label, support_url)
    if include_help:
        keyboard.button(MsgKey.HELP, HelpCallback())
    if include_support:
        keyboard.button("Связаться с поддержкой", SupportOpenCallback())
    return keyboard.as_markup()


def _is_valid_support_url(value: str | None) -> bool:
    return isinstance(value, str) and value.startswith(("https://", "http://"))

from collections.abc import Sequence
from html import escape
from typing import Protocol

from customer_bot.presentation.callbacks import (
    HelpCallback,
    RegistrationLegalAcceptCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _Document(Protocol):
    @property
    def document_type(self) -> str: ...

    @property
    def version(self) -> str: ...

    @property
    def content_url(self) -> str: ...


type _View = Sequence[_Document]


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        lines = [
            "<b>Регистрация заказчика</b>",
            "",
            "Перед началом нужно принять документы:",
        ]

        for document in self.data:
            title = escape(document.document_type)
            version = escape(document.version)
            url = escape(document.content_url)
            lines.append(f"• {title} {version}: {url}")
        lines.extend(("", "Нажмите кнопку ниже, если согласны продолжить."))
        return "\n".join(lines)

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        for index, document in enumerate(self.data, start=1):
            url = document.content_url
            if url.startswith("https://"):
                keyboard.url_button(f"Документ {index}", url)
        return (
            keyboard.button("Принять и продолжить", RegistrationLegalAcceptCallback())
            .button(MsgKey.HELP, HelpCallback())
            .as_markup()
        )

from html import escape

from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
)

type _View = str


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return f"⚠️ <b>Нужен текст</b>\n\n{escape(self.data)}"

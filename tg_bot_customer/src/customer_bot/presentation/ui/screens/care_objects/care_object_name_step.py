from html import escape
from typing import Protocol

from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
)


class _View(Protocol):
    @property
    def object_type_label(self) -> str: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return f"<b>{escape(self.data.object_type_label)}</b>\n\nВведите имя или короткое название."  # noqa: E501

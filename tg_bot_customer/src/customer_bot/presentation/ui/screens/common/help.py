from typing import Protocol

from customer_bot.presentation.ui.screens.common._keyboard import fallback_keyboard
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)


class _View(Protocol):
    @property
    def include_main_menu(self) -> bool: ...

    @property
    def legal_documents(self) -> tuple[object, ...]: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return (
            "<b>Помощь</b>\n\n"
            "Используйте кнопки под сообщениями. Если сценарий недоступен, вернитесь "
            "в главное меню и попробуйте позже."
        )

    def _build_keyboard(self) -> Markup:
        return fallback_keyboard(
            include_main_menu=True,
            legal_documents=self.data.legal_documents,
        )

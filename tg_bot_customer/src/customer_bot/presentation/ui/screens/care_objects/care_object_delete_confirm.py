from typing import Protocol

from customer_bot.presentation.callbacks import (
    CareObjectDeleteConfirmCallback,
    CareObjectsOpenCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _View(Protocol):
    @property
    def index(self) -> int: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return (
            "<b>Удалить карточку?</b>\n\n"
            "Карточка будет скрыта из профиля. Если она используется в активном "
            "заказе, вы не сможете удалить ее."
        )

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button(
                MsgKey.DELETE, CareObjectDeleteConfirmCallback(index=self.data.index)
            )
            .button(MsgKey.BACK_TO_LIST, CareObjectsOpenCallback())
            .as_markup()
        )

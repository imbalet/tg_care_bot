from collections.abc import Sequence
from html import escape
from typing import Protocol

from customer_bot.presentation.callbacks import (
    CareObjectAddCallback,
    CareObjectSelectCallback,
    MainMenuCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey

CARE_OBJECT_ADD_LABELS = {
    "child": MsgKey.ADD_CHILD,
    "ward": MsgKey.ADD_WARD,
    "pet": MsgKey.ADD_PET,
}


class _Category(Protocol):
    @property
    def name(self) -> str: ...


class _Items(Protocol):
    @property
    def display_name(self) -> str: ...


class _View(Protocol):
    @property
    def category(self) -> str: ...

    @property
    def object_type(self) -> str: ...

    @property
    def count(self) -> int: ...

    @property
    def items(self) -> Sequence[_Items]: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        title = self.data.category
        count = self.data.count
        if count == 0:
            return f"<b>{escape(title)}</b>\n\nДобавьте карточку до создания заказа."
        return f"<b>{escape(title)}</b>\n\nВыберите карточку или добавьте новую."

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        if self.data.object_type in CARE_OBJECT_ADD_LABELS:
            keyboard.button(
                CARE_OBJECT_ADD_LABELS[self.data.object_type],
                CareObjectAddCallback(object_type=self.data.object_type),
            )
        else:
            keyboard.button(
                MsgKey.ADD_CHILD, CareObjectAddCallback(object_type="child")
            )
            keyboard.button(MsgKey.ADD_WARD, CareObjectAddCallback(object_type="ward"))
            keyboard.button(MsgKey.ADD_PET, CareObjectAddCallback(object_type="pet"))
        for index, item in enumerate(self.data.items):
            display_name = item.display_name
            keyboard.button(str(display_name), CareObjectSelectCallback(index=index))
        return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()

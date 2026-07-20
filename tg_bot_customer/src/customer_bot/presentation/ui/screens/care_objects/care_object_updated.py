from typing import Protocol

from customer_bot.presentation.callbacks import (
    CareObjectsOpenCallback,
    MainMenuCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey

CARE_OBJECT_LIST_LABELS = {
    "child": "Мои дети",
    "ward": "Мои подопечные",
    "pet": "Мои питомцы",
}


class _View(Protocol):
    @property
    def object_type(self) -> str: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return "Карточка обновлена."

    def _build_keyboard(self) -> Markup:
        list_label = CARE_OBJECT_LIST_LABELS.get(self.data.object_type, "Объекты ухода")
        return (
            InlineKeyboardFactory()
            .button(MsgKey.MAIN_MENU, MainMenuCallback())
            .button(list_label, CareObjectsOpenCallback())
            .as_markup()
        )

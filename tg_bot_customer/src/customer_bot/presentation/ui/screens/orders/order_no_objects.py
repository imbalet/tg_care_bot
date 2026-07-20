from html import escape
from typing import Protocol

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderAddObjectCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey

CARE_OBJECT_SECTION_LABELS = {
    "child": "Мои дети",
    "ward": "Мои подопечные",
    "pet": "Мои питомцы",
}

CARE_OBJECT_ACCUSATIVE_LABELS = {
    "child": "ребенка",
    "ward": "подопечного",
    "pet": "питомца",
}


class _View(Protocol):
    @property
    def object_type(self) -> str: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        object_type = self.data.object_type
        object_label = CARE_OBJECT_ACCUSATIVE_LABELS.get(object_type, "карточку")
        section_label = CARE_OBJECT_SECTION_LABELS.get(object_type, "Мои дети")
        return (
            "<b>Новый заказ</b>\n\n"
            f"Нет подходящих карточек. Добавьте карточку {object_label} "
            f"в разделе «{escape(section_label)}»."
        )

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button("Добавить карточку", OrderAddObjectCallback())
            .button(MsgKey.MAIN_MENU, MainMenuCallback())
            .as_markup()
        )

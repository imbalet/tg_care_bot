from collections.abc import Sequence

from customer_bot.presentation.callbacks import (
    CategorySelectCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)

from ._category import CATEGORY_EMOJIS, _Category

type _View = Sequence[_Category]


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return "<b>Выберите направление</b>"

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        for category in self.data:
            code = category.code
            name = category.name
            care_object_type = category.care_object_type
            emoji = CATEGORY_EMOJIS.get(care_object_type, "")
            keyboard.button(
                f"{emoji} {name}".strip(),
                CategorySelectCallback(code=code),
            )
        return keyboard.as_markup()

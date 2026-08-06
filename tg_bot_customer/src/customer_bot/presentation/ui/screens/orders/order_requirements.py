from customer_bot.presentation.callbacks import (
    AddressAddCallback,
    CareObjectAddCallback,
    MainMenuCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import BaseScreen, Markup
from customer_bot.presentation.ui.texts.labels import MsgKey
from customer_bot.presentation.view_models import OrderRequirementsView

OBJECT_LABELS = {
    "child": "ребенка",
    "ward": "подопечного",
    "pet": "питомца",
}


class Screen(BaseScreen[OrderRequirementsView]):
    def _build_text(self) -> str:
        view = self.data
        missing: list[str] = []
        if not view.has_address:
            missing.append("адрес")
        if not view.has_care_object:
            missing.append(OBJECT_LABELS.get(view.object_type, "объект ухода"))
        missing_text = " и ".join(missing)
        return f"<b>Новый заказ</b>\n\nЧтобы создать заказ, добавьте {missing_text}."

    def _build_keyboard(self) -> Markup:
        view = self.data
        keyboard = InlineKeyboardFactory()
        if not view.has_care_object:
            keyboard.button(
                f"Добавить {OBJECT_LABELS.get(view.object_type, 'объект ухода')}",
                CareObjectAddCallback(object_type=view.object_type),
            )
        if not view.has_address:
            keyboard.button(MsgKey.ADD_ADDRESS, AddressAddCallback())
        return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()

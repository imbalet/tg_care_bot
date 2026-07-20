from html import escape

from customer_bot.presentation.callbacks import (
    AddressesOpenCallback,
    CareObjectsOpenCallback,
    CategoryChangeCallback,
    HelpCallback,
    OrderCreateCallback,
    OrdersListCallback,
    ProfileOpenCallback,
    ServicesPricesCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey

from ._category import CATEGORY_EMOJIS, _Category

CARE_OBJECT_LIST_LABELS = {
    "child": "Мои дети",
    "ward": "Мои подопечные",
    "pet": "Мои питомцы",
}


class Screen(BaseScreen[_Category]):
    def _build_text(self) -> str:
        name = self.data.name
        care_object_type = self.data.care_object_type
        emoji = CATEGORY_EMOJIS.get(care_object_type, "")
        title = f"{emoji} {name}".strip()
        return f"<b>{escape(title)}</b>"

    def _build_keyboard(self) -> Markup:
        care_object_type = self.data.care_object_type
        category_code = self.data.code
        care_label = CARE_OBJECT_LIST_LABELS.get(care_object_type, "Объекты ухода")
        return (
            InlineKeyboardFactory()
            .button(MsgKey.CREATE_ORDER, OrderCreateCallback())
            .button(MsgKey.MY_ORDERS, OrdersListCallback())
            .button(care_label, CareObjectsOpenCallback(category_code=category_code))
            .button(MsgKey.SERVICES_PRICES, ServicesPricesCallback())
            .button(MsgKey.ADDRESS, AddressesOpenCallback())
            .button(MsgKey.PROFILE, ProfileOpenCallback())
            .button(MsgKey.HELP, HelpCallback())
            .button(MsgKey.SWITCH_CATEGORY, CategoryChangeCallback())
            .as_markup()
        )

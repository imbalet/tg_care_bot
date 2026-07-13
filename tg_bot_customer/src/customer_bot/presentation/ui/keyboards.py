from collections.abc import Sequence
from typing import Protocol

from aiogram.types import InlineKeyboardMarkup

from customer_bot.presentation.callbacks import (
    AddressAddCallback,
    AddressCityCallback,
    AddressDeleteCallback,
    AddressesOpenCallback,
    AddressSelectCallback,
    AddressSkipCallback,
    AddressSuggestionCallback,
    CareObjectAddCallback,
    CareObjectAgeCallback,
    CareObjectDeleteCallback,
    CareObjectEditCallback,
    CareObjectMobilityCallback,
    CareObjectSelectCallback,
    CareObjectSizeCallback,
    CareObjectSkipCallback,
    CareObjectsOpenCallback,
    HelpCallback,
    MainMenuCallback,
    OrderAddressCallback,
    OrderCommentSkipCallback,
    OrderCreateCallback,
    OrderObjectCallback,
    OrderPhotoConsentCallback,
    OrderPublishDirectCallback,
    OrderPublishPoolCallback,
    OrderServiceCallback,
    OrdersListCallback,
    ProfileOpenCallback,
    RegistrationCityCallback,
    RegistrationConfirmCallback,
    RegistrationContactCallback,
    RegistrationEditCallback,
    RegistrationLegalAcceptCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.labels import MsgKey, text

CARE_OBJECT_TYPE_LABELS = {
    "child": "Ребенок",
    "ward": "Подопечный",
    "pet": "Питомец",
}

CARE_OBJECT_AGE_LABELS = {
    "infant": "До 1 года",
    "preschool": "Дошкольник",
    "school_age": "Школьник",
    "teenager": "Подросток",
    "adult": "Взрослый",
    "senior": "Пожилой",
    "unknown": "Не указано",
}

CARE_OBJECT_SIZE_LABELS = {
    "small": "Маленький",
    "medium": "Средний",
    "large": "Крупный",
    "unknown": "Не указано",
}


class CityButtonView(Protocol):
    @property
    def name(self) -> str:
        pass


def legal_acceptance_keyboard(documents: Sequence[object] = ()) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    for index, document in enumerate(documents, start=1):
        url = str(getattr(document, "content_url", ""))
        if url.startswith("https://"):
            keyboard.url_button(f"Документ {index}", url)
    return (
        keyboard.button("Принять и продолжить", RegistrationLegalAcceptCallback())
        .button(MsgKey.HELP, HelpCallback())
        .as_markup()
    )


def select_city_keyboard(cities: Sequence[CityButtonView]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    for index, city in enumerate(cities):
        keyboard.button(city.name, RegistrationCityCallback(index=index))
    return keyboard.as_markup()


def contact_methods_keyboard() -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button("Telegram", RegistrationContactCallback(method="telegram"))
        .button("Телефон", RegistrationContactCallback(method="phone"))
        .button("Telegram и телефон", RegistrationContactCallback(method="both"))
        .as_markup()
    )


def registration_summary_keyboard() -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button(MsgKey.CONFIRM, RegistrationConfirmCallback())
        .button(MsgKey.EDIT, RegistrationEditCallback())
        .as_markup()
    )


def main_menu_keyboard(topic_kind: str | None = None) -> InlineKeyboardMarkup:
    if topic_kind == "notifications":
        return InlineKeyboardFactory().button(MsgKey.HELP, HelpCallback()).as_markup()
    care_label = {
        "children": text(MsgKey.CHILDREN),
        "wards": text(MsgKey.WARDS),
        "pets": text(MsgKey.PETS),
    }.get(topic_kind or "", "Карточки")
    return (
        InlineKeyboardFactory()
        .button(MsgKey.CREATE_ORDER, OrderCreateCallback())
        .button(MsgKey.MY_ORDERS, OrdersListCallback())
        .button(care_label, CareObjectsOpenCallback())
        .button(MsgKey.ADDRESS, AddressesOpenCallback())
        .button(MsgKey.PROFILE, ProfileOpenCallback())
        .button(MsgKey.HELP, HelpCallback())
        .as_markup()
    )


def fallback_keyboard(*, include_main_menu: bool = True) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    if include_main_menu:
        keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback())
    return keyboard.button(MsgKey.HELP, HelpCallback()).as_markup()


def care_objects_keyboard(items: Sequence[object]) -> InlineKeyboardMarkup:
    keyboard = (
        InlineKeyboardFactory()
        .button(MsgKey.ADD_CHILD, CareObjectAddCallback(object_type="child"))
        .button(MsgKey.ADD_WARD, CareObjectAddCallback(object_type="ward"))
        .button(MsgKey.ADD_PET, CareObjectAddCallback(object_type="pet"))
    )
    for index, item in enumerate(items):
        display_name = getattr(item, "display_name", f"#{index + 1}")
        keyboard.button(str(display_name), CareObjectSelectCallback(index=index))
    return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()


def care_object_card_keyboard(index: int) -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button(MsgKey.EDIT_NAME, CareObjectEditCallback(index=index))
        .button(MsgKey.DELETE, CareObjectDeleteCallback(index=index))
        .button(MsgKey.BACK_TO_LIST, CareObjectsOpenCallback())
        .as_markup()
    )


def care_object_age_keyboard(object_type: str) -> InlineKeyboardMarkup:
    age_keys = (
        ("infant", "preschool", "school_age", "teenager")
        if object_type == "child"
        else ("adult", "senior", "unknown")
    )
    keyboard = InlineKeyboardFactory()
    for age_group in age_keys:
        keyboard.button(
            CARE_OBJECT_AGE_LABELS[age_group],
            CareObjectAgeCallback(age_group=age_group),
        )
    return keyboard.as_markup()


def care_object_size_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    for value, label in CARE_OBJECT_SIZE_LABELS.items():
        keyboard.button(label, CareObjectSizeCallback(size=value))
    return keyboard.as_markup()


def care_object_mobility_keyboard() -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button("Нужна помощь", CareObjectMobilityCallback(value="yes"))
        .button("Не нужна", CareObjectMobilityCallback(value="no"))
        .as_markup()
    )


def care_object_skip_keyboard() -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button(MsgKey.SKIP, CareObjectSkipCallback())
        .as_markup()
    )


def addresses_keyboard(items: Sequence[object]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory().button(MsgKey.ADD_ADDRESS, AddressAddCallback())
    for index, item in enumerate(items):
        address_text = getattr(item, "address_text", f"#{index + 1}")
        keyboard.button(str(address_text), AddressSelectCallback(index=index))
    return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()


def address_card_keyboard(index: int) -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button(MsgKey.DELETE, AddressDeleteCallback(index=index))
        .button(MsgKey.BACK_TO_LIST, AddressesOpenCallback())
        .as_markup()
    )


def address_city_keyboard(cities: Sequence[CityButtonView]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    for index, city in enumerate(cities):
        keyboard.button(city.name, AddressCityCallback(index=index))
    return keyboard.as_markup()


def address_suggestions_keyboard(suggestions: Sequence[object]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    for index, suggestion in enumerate(suggestions):
        keyboard.button(
            str(getattr(suggestion, "value", index + 1)),
            AddressSuggestionCallback(index=index),
        )
    return keyboard.as_markup()


def address_skip_keyboard() -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory().button(MsgKey.SKIP, AddressSkipCallback()).as_markup()
    )


def order_services_keyboard(items: Sequence[object]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    for index, item in enumerate(items):
        keyboard.button(
            _item_label(item, "name", index), OrderServiceCallback(index=index)
        )
    return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()


def order_objects_keyboard(items: Sequence[object]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    for index, item in enumerate(items):
        keyboard.button(
            _item_label(item, "display_name", index),
            OrderObjectCallback(index=index),
        )
    return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()


def order_addresses_keyboard(items: Sequence[object]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    for index, item in enumerate(items):
        keyboard.button(
            _item_label(item, "address_text", index),
            OrderAddressCallback(index=index),
        )
    return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()


def order_photo_consent_keyboard() -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button(MsgKey.ALLOW, OrderPhotoConsentCallback(value="yes"))
        .button(MsgKey.DENY, OrderPhotoConsentCallback(value="no"))
        .as_markup()
    )


def order_comment_skip_keyboard() -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button(MsgKey.SKIP, OrderCommentSkipCallback())
        .as_markup()
    )


def order_publish_keyboard(performers: Sequence[object]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory().button(
        MsgKey.PUBLISH_POOL, OrderPublishPoolCallback()
    )
    for index, performer in enumerate(performers):
        keyboard.button(
            f"Предложить: {_item_label(performer, 'full_name', index)}",
            OrderPublishDirectCallback(index=index),
        )
    return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()


def _item_label(item: object, key: str, index: int) -> str:
    if isinstance(item, dict):
        value = item.get(key)
        return str(value) if value is not None else f"#{index + 1}"
    return str(getattr(item, key, f"#{index + 1}"))

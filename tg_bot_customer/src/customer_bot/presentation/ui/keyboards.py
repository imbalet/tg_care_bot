from collections.abc import Sequence
from typing import Protocol

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

REGISTRATION_ACCEPT_LEGAL = "registration:legal:accept"
REGISTRATION_CITY_PREFIX = "registration:city:"
REGISTRATION_CONTACT_PREFIX = "registration:contact:"
REGISTRATION_CONFIRM = "registration:summary:confirm"
REGISTRATION_EDIT = "registration:summary:edit"
MAIN_MENU = "navigation:main_menu"
HELP = "navigation:help"
CARE_OBJECTS_OPEN = "care_objects:open"
CARE_OBJECT_ADD_PREFIX = "care_objects:add:"
CARE_OBJECT_SELECT_PREFIX = "care_objects:select:"
CARE_OBJECT_EDIT_PREFIX = "care_objects:edit:"
CARE_OBJECT_DELETE_PREFIX = "care_objects:delete:"
CARE_OBJECT_AGE_PREFIX = "care_objects:age:"
CARE_OBJECT_SIZE_PREFIX = "care_objects:size:"
CARE_OBJECT_MOBILITY_PREFIX = "care_objects:mobility:"
CARE_OBJECT_SKIP = "care_objects:skip"
ADDRESSES_OPEN = "addresses:open"
ADDRESS_ADD = "addresses:add"
ADDRESS_SELECT_PREFIX = "addresses:select:"
ADDRESS_DELETE_PREFIX = "addresses:delete:"
ADDRESS_CITY_PREFIX = "addresses:city:"
ADDRESS_SUGGESTION_PREFIX = "addresses:suggestion:"
ADDRESS_SKIP = "addresses:skip"
ORDER_CREATE = "orders:create"
ORDER_SERVICE_PREFIX = "orders:service:"
ORDER_OBJECT_PREFIX = "orders:object:"
ORDER_ADDRESS_PREFIX = "orders:address:"
ORDER_PHOTO_CONSENT_PREFIX = "orders:photo_consent:"
ORDER_COMMENT_SKIP = "orders:comment:skip"
ORDER_PUBLISH_POOL = "orders:publish:pool"
ORDER_PUBLISH_DIRECT_PREFIX = "orders:publish:direct:"

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
    rows = [
        [
            InlineKeyboardButton(
                text=f"Документ {index}",
                url=str(getattr(document, "content_url", "")),
            ),
        ]
        for index, document in enumerate(documents, start=1)
        if str(getattr(document, "content_url", "")).startswith("https://")
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="Принять и продолжить",
                callback_data=REGISTRATION_ACCEPT_LEGAL,
            ),
        ],
    )
    rows.append([InlineKeyboardButton(text="Помощь", callback_data=HELP)])
    return InlineKeyboardMarkup(
        inline_keyboard=rows,
    )


def select_city_keyboard(cities: Sequence[CityButtonView]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=city.name,
                    callback_data=f"{REGISTRATION_CITY_PREFIX}{index}",
                ),
            ]
            for index, city in enumerate(cities)
        ],
    )


def contact_methods_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Telegram",
                    callback_data=f"{REGISTRATION_CONTACT_PREFIX}telegram",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Телефон",
                    callback_data=f"{REGISTRATION_CONTACT_PREFIX}phone",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Telegram и телефон",
                    callback_data=f"{REGISTRATION_CONTACT_PREFIX}both",
                ),
            ],
        ],
    )


def registration_summary_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить",
                    callback_data=REGISTRATION_CONFIRM,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Редактировать", callback_data=REGISTRATION_EDIT
                )
            ],
        ],
    )


def main_menu_keyboard(topic_kind: str | None = None) -> InlineKeyboardMarkup:
    if topic_kind == "notifications":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Помощь", callback_data=HELP)],
            ],
        )
    care_label = {
        "children": "Дети",
        "wards": "Подопечные",
        "pets": "Питомцы",
    }.get(topic_kind or "", "Карточки")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Создать заказ", callback_data=ORDER_CREATE)],
            [InlineKeyboardButton(text="Мои заказы", callback_data="orders:list")],
            [
                InlineKeyboardButton(
                    text=care_label,
                    callback_data=CARE_OBJECTS_OPEN,
                ),
            ],
            [InlineKeyboardButton(text="Адреса", callback_data=ADDRESSES_OPEN)],
            [InlineKeyboardButton(text="Профиль", callback_data="profile:open")],
            [InlineKeyboardButton(text="Помощь", callback_data=HELP)],
        ],
    )


def fallback_keyboard(*, include_main_menu: bool = True) -> InlineKeyboardMarkup:
    rows = []
    if include_main_menu:
        rows.append(
            [InlineKeyboardButton(text="Главное меню", callback_data=MAIN_MENU)]
        )
    rows.append([InlineKeyboardButton(text="Помощь", callback_data=HELP)])
    return InlineKeyboardMarkup(
        inline_keyboard=rows,
    )


def care_objects_keyboard(items: Sequence[object]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="Добавить ребенка",
                callback_data=f"{CARE_OBJECT_ADD_PREFIX}child",
            ),
        ],
        [
            InlineKeyboardButton(
                text="Добавить подопечного",
                callback_data=f"{CARE_OBJECT_ADD_PREFIX}ward",
            ),
        ],
        [
            InlineKeyboardButton(
                text="Добавить питомца",
                callback_data=f"{CARE_OBJECT_ADD_PREFIX}pet",
            ),
        ],
    ]
    for index, item in enumerate(items):
        display_name = getattr(item, "display_name", f"#{index + 1}")
        rows.append(
            [
                InlineKeyboardButton(
                    text=str(display_name),
                    callback_data=f"{CARE_OBJECT_SELECT_PREFIX}{index}",
                ),
            ],
        )
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data=MAIN_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def care_object_card_keyboard(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Редактировать имя",
                    callback_data=f"{CARE_OBJECT_EDIT_PREFIX}{index}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Удалить",
                    callback_data=f"{CARE_OBJECT_DELETE_PREFIX}{index}",
                ),
            ],
            [InlineKeyboardButton(text="К списку", callback_data=CARE_OBJECTS_OPEN)],
        ],
    )


def care_object_age_keyboard(object_type: str) -> InlineKeyboardMarkup:
    age_keys = (
        ("infant", "preschool", "school_age", "teenager")
        if object_type == "child"
        else ("adult", "senior", "unknown")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=CARE_OBJECT_AGE_LABELS[age_group],
                    callback_data=f"{CARE_OBJECT_AGE_PREFIX}{age_group}",
                ),
            ]
            for age_group in age_keys
        ],
    )


def care_object_size_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{CARE_OBJECT_SIZE_PREFIX}{value}",
                ),
            ]
            for value, label in CARE_OBJECT_SIZE_LABELS.items()
        ],
    )


def care_object_mobility_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Нужна помощь",
                    callback_data=f"{CARE_OBJECT_MOBILITY_PREFIX}yes",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Не нужна",
                    callback_data=f"{CARE_OBJECT_MOBILITY_PREFIX}no",
                ),
            ],
        ],
    )


def care_object_skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data=CARE_OBJECT_SKIP)],
        ],
    )


def addresses_keyboard(items: Sequence[object]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="Добавить адрес", callback_data=ADDRESS_ADD)]]
    for index, item in enumerate(items):
        address_text = getattr(item, "address_text", f"#{index + 1}")
        rows.append(
            [
                InlineKeyboardButton(
                    text=str(address_text),
                    callback_data=f"{ADDRESS_SELECT_PREFIX}{index}",
                ),
            ],
        )
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data=MAIN_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def address_card_keyboard(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Удалить",
                    callback_data=f"{ADDRESS_DELETE_PREFIX}{index}",
                ),
            ],
            [InlineKeyboardButton(text="К списку", callback_data=ADDRESSES_OPEN)],
        ],
    )


def address_city_keyboard(cities: Sequence[CityButtonView]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=city.name,
                    callback_data=f"{ADDRESS_CITY_PREFIX}{index}",
                ),
            ]
            for index, city in enumerate(cities)
        ],
    )


def address_suggestions_keyboard(suggestions: Sequence[object]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=str(getattr(suggestion, "value", index + 1)),
                    callback_data=f"{ADDRESS_SUGGESTION_PREFIX}{index}",
                ),
            ]
            for index, suggestion in enumerate(suggestions)
        ],
    )


def address_skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data=ADDRESS_SKIP)],
        ],
    )


def order_services_keyboard(items: Sequence[object]) -> InlineKeyboardMarkup:
    rows = []
    for index, item in enumerate(items):
        rows.append(
            [
                InlineKeyboardButton(
                    text=_item_label(item, "name", index),
                    callback_data=f"{ORDER_SERVICE_PREFIX}{index}",
                ),
            ],
        )
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data=MAIN_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_objects_keyboard(items: Sequence[object]) -> InlineKeyboardMarkup:
    rows = []
    for index, item in enumerate(items):
        rows.append(
            [
                InlineKeyboardButton(
                    text=_item_label(item, "display_name", index),
                    callback_data=f"{ORDER_OBJECT_PREFIX}{index}",
                ),
            ],
        )
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data=MAIN_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_addresses_keyboard(items: Sequence[object]) -> InlineKeyboardMarkup:
    rows = []
    for index, item in enumerate(items):
        rows.append(
            [
                InlineKeyboardButton(
                    text=_item_label(item, "address_text", index),
                    callback_data=f"{ORDER_ADDRESS_PREFIX}{index}",
                ),
            ],
        )
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data=MAIN_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_photo_consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Разрешаю",
                    callback_data=f"{ORDER_PHOTO_CONSENT_PREFIX}yes",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Не разрешаю",
                    callback_data=f"{ORDER_PHOTO_CONSENT_PREFIX}no",
                ),
            ],
        ],
    )


def order_comment_skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data=ORDER_COMMENT_SKIP)],
        ],
    )


def order_publish_keyboard(performers: Sequence[object]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="Опубликовать в пул", callback_data=ORDER_PUBLISH_POOL
            )
        ]
    ]
    for index, performer in enumerate(performers):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"Предложить: {_item_label(performer, 'full_name', index)}",
                    callback_data=f"{ORDER_PUBLISH_DIRECT_PREFIX}{index}",
                ),
            ],
        )
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data=MAIN_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _item_label(item: object, key: str, index: int) -> str:
    if isinstance(item, dict):
        value = item.get(key)
        return str(value) if value is not None else f"#{index + 1}"
    return str(getattr(item, key, f"#{index + 1}"))

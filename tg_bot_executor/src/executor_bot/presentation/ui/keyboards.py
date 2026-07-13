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
WORK_ADDRESSES_OPEN = "work_addresses:open"
WORK_ADDRESS_ADD = "work_addresses:add"
WORK_ADDRESS_SELECT_PREFIX = "work_addresses:select:"
WORK_ADDRESS_DELETE_PREFIX = "work_addresses:delete:"
WORK_ADDRESS_CURRENT_PREFIX = "work_addresses:current:"
WORK_ADDRESS_CITY_PREFIX = "work_addresses:city:"
WORK_ADDRESS_SUGGESTION_PREFIX = "work_addresses:suggestion:"
WORK_ADDRESS_SKIP = "work_addresses:skip"
AVATAR_OPEN = "avatar:open"
AVATAR_UPLOAD = "avatar:upload"
AVATAR_DELETE = "avatar:delete"
SERVICES_OPEN = "services:open"
SERVICES_TOGGLE_PREFIX = "services:toggle:"
SERVICES_LIMIT_PREFIX = "services:limit:"
ACCEPTING_ON = "services:accepting:on"
ACCEPTING_OFF = "services:accepting:off"
CALENDAR_OPEN = "calendar:open"
CALENDAR_EVERY_DAY = "calendar:schedule:every_day"
CALENDAR_WEEKDAYS = "calendar:schedule:weekdays"
CALENDAR_WEEKENDS = "calendar:schedule:weekends"
CALENDAR_UNAVAILABLE_TOMORROW = "calendar:override:unavailable_tomorrow"


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
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Доступные заказы", callback_data="orders:feed"
                )
            ],
            [InlineKeyboardButton(text="Мои заказы", callback_data="orders:list")],
            [InlineKeyboardButton(text="Услуги", callback_data=SERVICES_OPEN)],
            [InlineKeyboardButton(text="Календарь", callback_data=CALENDAR_OPEN)],
            [
                InlineKeyboardButton(
                    text="Рабочий адрес",
                    callback_data=WORK_ADDRESSES_OPEN,
                ),
            ],
            [InlineKeyboardButton(text="Аватар", callback_data=AVATAR_OPEN)],
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


def work_addresses_keyboard(items: Sequence[object]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Добавить адрес", callback_data=WORK_ADDRESS_ADD)]
    ]
    for index, item in enumerate(items):
        address_text = getattr(item, "address_text", f"#{index + 1}")
        rows.append(
            [
                InlineKeyboardButton(
                    text=str(address_text),
                    callback_data=f"{WORK_ADDRESS_SELECT_PREFIX}{index}",
                ),
            ],
        )
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data=MAIN_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def work_address_card_keyboard(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Сделать текущим",
                    callback_data=f"{WORK_ADDRESS_CURRENT_PREFIX}{index}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Удалить",
                    callback_data=f"{WORK_ADDRESS_DELETE_PREFIX}{index}",
                ),
            ],
            [InlineKeyboardButton(text="К списку", callback_data=WORK_ADDRESSES_OPEN)],
        ],
    )


def work_address_city_keyboard(
    cities: Sequence[CityButtonView],
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=city.name,
                    callback_data=f"{WORK_ADDRESS_CITY_PREFIX}{index}",
                ),
            ]
            for index, city in enumerate(cities)
        ],
    )


def work_address_suggestions_keyboard(
    suggestions: Sequence[object],
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=str(getattr(suggestion, "value", index + 1)),
                    callback_data=f"{WORK_ADDRESS_SUGGESTION_PREFIX}{index}",
                ),
            ]
            for index, suggestion in enumerate(suggestions)
        ],
    )


def work_address_skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data=WORK_ADDRESS_SKIP)],
        ],
    )


def avatar_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Загрузить", callback_data=AVATAR_UPLOAD)],
            [InlineKeyboardButton(text="Удалить", callback_data=AVATAR_DELETE)],
            [InlineKeyboardButton(text="Главное меню", callback_data=MAIN_MENU)],
        ],
    )


def services_keyboard(items: Sequence[object]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="Принимать заказы",
                callback_data=ACCEPTING_ON,
            ),
            InlineKeyboardButton(
                text="Пауза",
                callback_data=ACCEPTING_OFF,
            ),
        ],
    ]
    for index, item in enumerate(items):
        enabled = bool(getattr(item, "is_enabled", False))
        name = str(getattr(item, "service_name", f"#{index + 1}"))
        toggle_text = "Отключить" if enabled else "Включить"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{toggle_text}: {name}",
                    callback_data=f"{SERVICES_TOGGLE_PREFIX}{index}",
                ),
            ],
        )
        current_limit = int(getattr(item, "performer_max_objects", 1))
        if current_limit > 1:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"Лимит -1: {name}",
                        callback_data=f"{SERVICES_LIMIT_PREFIX}{index}",
                    ),
                ],
            )
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data=MAIN_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def calendar_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Каждый день 09-18",
                    callback_data=CALENDAR_EVERY_DAY,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Будни 09-18",
                    callback_data=CALENDAR_WEEKDAYS,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Выходные 09-18",
                    callback_data=CALENDAR_WEEKENDS,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Завтра недоступен",
                    callback_data=CALENDAR_UNAVAILABLE_TOMORROW,
                ),
            ],
            [InlineKeyboardButton(text="Главное меню", callback_data=MAIN_MENU)],
        ],
    )


__all__ = [
    "HELP",
    "MAIN_MENU",
    "AVATAR_DELETE",
    "AVATAR_OPEN",
    "AVATAR_UPLOAD",
    "ACCEPTING_OFF",
    "ACCEPTING_ON",
    "CALENDAR_EVERY_DAY",
    "CALENDAR_OPEN",
    "CALENDAR_UNAVAILABLE_TOMORROW",
    "CALENDAR_WEEKDAYS",
    "CALENDAR_WEEKENDS",
    "REGISTRATION_ACCEPT_LEGAL",
    "REGISTRATION_CITY_PREFIX",
    "REGISTRATION_CONFIRM",
    "REGISTRATION_CONTACT_PREFIX",
    "REGISTRATION_EDIT",
    "WORK_ADDRESSES_OPEN",
    "WORK_ADDRESS_ADD",
    "WORK_ADDRESS_CITY_PREFIX",
    "WORK_ADDRESS_CURRENT_PREFIX",
    "WORK_ADDRESS_DELETE_PREFIX",
    "WORK_ADDRESS_SELECT_PREFIX",
    "WORK_ADDRESS_SKIP",
    "WORK_ADDRESS_SUGGESTION_PREFIX",
    "SERVICES_LIMIT_PREFIX",
    "SERVICES_OPEN",
    "SERVICES_TOGGLE_PREFIX",
    "avatar_keyboard",
    "calendar_keyboard",
    "contact_methods_keyboard",
    "fallback_keyboard",
    "legal_acceptance_keyboard",
    "main_menu_keyboard",
    "registration_summary_keyboard",
    "select_city_keyboard",
    "services_keyboard",
    "work_address_card_keyboard",
    "work_address_city_keyboard",
    "work_address_skip_keyboard",
    "work_address_suggestions_keyboard",
    "work_addresses_keyboard",
]

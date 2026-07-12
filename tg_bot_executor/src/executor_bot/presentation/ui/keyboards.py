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


class CityButtonView(Protocol):
    @property
    def name(self) -> str:
        pass


def legal_acceptance_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Принять и продолжить",
                    callback_data=REGISTRATION_ACCEPT_LEGAL,
                ),
            ],
            [InlineKeyboardButton(text="Помощь", callback_data=HELP)],
        ],
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


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Доступные заказы", callback_data="orders:feed"
                )
            ],
            [InlineKeyboardButton(text="Мои заказы", callback_data="orders:list")],
            [InlineKeyboardButton(text="Календарь", callback_data="calendar:open")],
            [
                InlineKeyboardButton(
                    text="Рабочий адрес",
                    callback_data=WORK_ADDRESSES_OPEN,
                ),
            ],
            [InlineKeyboardButton(text="Профиль", callback_data="profile:open")],
            [InlineKeyboardButton(text="Помощь", callback_data=HELP)],
        ],
    )


def fallback_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Главное меню", callback_data=MAIN_MENU)],
            [InlineKeyboardButton(text="Помощь", callback_data=HELP)],
        ],
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


__all__ = [
    "HELP",
    "MAIN_MENU",
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
    "contact_methods_keyboard",
    "fallback_keyboard",
    "legal_acceptance_keyboard",
    "main_menu_keyboard",
    "registration_summary_keyboard",
    "select_city_keyboard",
    "work_address_card_keyboard",
    "work_address_city_keyboard",
    "work_address_skip_keyboard",
    "work_address_suggestions_keyboard",
    "work_addresses_keyboard",
]

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


__all__ = [
    "HELP",
    "MAIN_MENU",
    "REGISTRATION_ACCEPT_LEGAL",
    "REGISTRATION_CITY_PREFIX",
    "REGISTRATION_CONFIRM",
    "REGISTRATION_CONTACT_PREFIX",
    "REGISTRATION_EDIT",
    "contact_methods_keyboard",
    "fallback_keyboard",
    "legal_acceptance_keyboard",
    "main_menu_keyboard",
    "registration_summary_keyboard",
    "select_city_keyboard",
]

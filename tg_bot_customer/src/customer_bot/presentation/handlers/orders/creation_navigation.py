from datetime import date
from typing import cast

from aiogram.types import InlineKeyboardMarkup
from aiogram_calendar import SimpleCalendar


def start_calendar() -> SimpleCalendar:
    return SimpleCalendar()


async def start_calendar_keyboard() -> InlineKeyboardMarkup:
    return cast(InlineKeyboardMarkup, await start_calendar().start_calendar())


def start_time_value(value: str) -> str:
    if ":" in value:
        return value
    if len(value) == 4 and value.isdigit():
        return f"{value[:2]}:{value[2:]}"
    return value


def format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")

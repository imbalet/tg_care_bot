from typing import Protocol

from customer_bot.presentation.callbacks import (
    CareObjectAgeCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)

CARE_OBJECT_AGE_LABELS = {
    "infant": "До 1 года",
    "preschool": "Дошкольник",
    "school_age": "Школьник",
    "teenager": "Подросток",
    "adult": "Взрослый",
    "senior": "Пожилой",
    "unknown": "Не указано",
}


class _View(Protocol):
    @property
    def object_type(self) -> str: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return "<b>Возрастная группа</b>\n\nВыберите подходящий вариант."

    def _build_keyboard(self) -> Markup:
        age_keys = {
            "child": ("infant", "preschool", "school_age", "teenager"),
            "ward": ("adult", "senior", "unknown"),
        }.get(self.data.object_type, ())
        keyboard = InlineKeyboardFactory()
        for age_group in age_keys:
            keyboard.button(
                CARE_OBJECT_AGE_LABELS[age_group],
                CareObjectAgeCallback(age_group=age_group),
            )
        return keyboard.as_markup()

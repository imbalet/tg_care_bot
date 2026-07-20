from html import escape
from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderDirectBackCallback,
    OrderDirectNextCallback,
    OrderDirectPreviousCallback,
    OrderPublishDirectCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import BaseScreen, Markup


class _Performer(Protocol):
    @property
    def performer_id(self) -> UUID: ...

    @property
    def full_name(self) -> str: ...

    @property
    def service_name(self) -> str: ...

    @property
    def distance_km(self) -> object: ...


class _View(Protocol):
    @property
    def performer(self) -> _Performer: ...

    @property
    def index(self) -> int: ...

    @property
    def total(self) -> int: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        performer = self.data.performer
        distance = performer.distance_km
        distance_text = (
            f"{distance} км" if distance is not None else "Расстояние неизвестно"
        )
        return "\n".join(
            (
                "<b>Выбор исполнителя</b>",
                "",
                f"Исполнитель: {escape(performer.full_name)}",
                f"Услуга: {escape(performer.service_name)}",
                f"Расстояние: {escape(distance_text)}",
                "",
                f"Карточка {self.data.index + 1} из {self.data.total}",
            ),
        )

    def _build_keyboard(self) -> Markup:
        performer = self.data.performer
        keyboard = InlineKeyboardFactory()
        keyboard.button(
            "Выбрать исполнителя",
            OrderPublishDirectCallback(performer_id=performer.performer_id),
        )
        keyboard.row()
        if self.data.index > 0:
            keyboard.button("Предыдущий", OrderDirectPreviousCallback())
        if self.data.index + 1 < self.data.total:
            keyboard.button("Следующий", OrderDirectNextCallback())
        keyboard.row()
        keyboard.button("Назад", OrderDirectBackCallback())
        keyboard.button("Главное меню", MainMenuCallback())
        return keyboard.as_markup()

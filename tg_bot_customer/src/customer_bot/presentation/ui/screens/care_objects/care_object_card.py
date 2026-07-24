from html import escape
from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    CareObjectDeleteCallback,
    CareObjectEditCallback,
    CareObjectsOpenCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey

OBJECT_CARD_TITLES = {
    "Ребёнок": "Карточка ребёнка",
    "Подопечный": "Карточка подопечного",
    "Питомец": "Карточка питомца",
}


class _View(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def object_type(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    @property
    def age_group(self) -> str: ...

    @property
    def species(self) -> str | None: ...

    @property
    def breed(self) -> str | None: ...

    @property
    def pet_size(self) -> str | None: ...

    @property
    def mobility_assistance_required(self) -> bool | None: ...

    @property
    def routine_notes(self) -> str | None: ...

    @property
    def behavior_notes(self) -> str | None: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        object_type = escape(self.data.object_type)
        display_name = escape(self.data.display_name)
        age_group = escape(self.data.age_group)
        species = escape(self.data.species) if self.data.species else None
        breed = escape(self.data.breed) if self.data.breed else None
        pet_size = escape(self.data.pet_size) if self.data.pet_size else None
        mobility = self.data.mobility_assistance_required
        routine_notes = (
            escape(self.data.routine_notes) if self.data.routine_notes else None
        )
        behavior_notes = (
            escape(self.data.behavior_notes) if self.data.behavior_notes else None
        )
        lines = [
            f"<b>{OBJECT_CARD_TITLES.get(self.data.object_type, 'Карточка')}</b>",
            "",
            f"Тип: {object_type}",
            f"Имя: {display_name}",
            f"Возраст: {age_group}",
        ]
        if species is not None and self.data.object_type == "Питомец":
            lines.append(f"Вид: {species}")
        if breed is not None and self.data.object_type == "Питомец":
            lines.append(f"Порода: {breed}")
        if pet_size is not None and self.data.object_type == "Питомец":
            lines.append(f"Размер: {pet_size}")
        if mobility is not None and self.data.object_type == "Подопечный":
            lines.append(f"Помощь с передвижением: {'да' if mobility else 'нет'}")
        if routine_notes is not None:
            lines.append(f"Комментарий по уходу: {routine_notes}")
        if behavior_notes is not None:
            lines.append(f"Особенности поведения: {behavior_notes}")
        return "\n".join(lines)

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button(
                MsgKey.EDIT_NAME,
                CareObjectEditCallback(care_object_id=UUID(str(self.data.id))),
            )
            .button(
                MsgKey.DELETE,
                CareObjectDeleteCallback(care_object_id=UUID(str(self.data.id))),
            )
            .button(MsgKey.BACK_TO_LIST, CareObjectsOpenCallback())
            .as_markup()
        )

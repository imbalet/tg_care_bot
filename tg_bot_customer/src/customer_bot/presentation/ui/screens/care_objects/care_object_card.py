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
    def species(self) -> str: ...

    @property
    def breed(self) -> str: ...

    @property
    def pet_size(self) -> str: ...

    @property
    def mobility_assistance_required(self) -> bool: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        object_type = escape(self.data.object_type)
        display_name = escape(self.data.display_name)
        age_group = escape(self.data.age_group)
        species = escape(self.data.species)
        breed = escape(self.data.breed)
        pet_size = escape(self.data.pet_size)
        mobility = self.data.mobility_assistance_required
        lines = [
            "<b>Карточка объекта ухода</b>",
            "",
            f"Тип: {object_type}",
            f"Имя: {display_name}",
            f"Возраст: {age_group}",
        ]
        if isinstance(species, str):
            lines.append(f"Вид: {species}")
        if isinstance(breed, str):
            lines.append(f"Порода: {breed}")
        if isinstance(pet_size, str):
            lines.append(f"Размер: {pet_size}")
        if isinstance(mobility, bool):
            lines.append(f"Помощь с передвижением: {'да' if mobility else 'нет'}")
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

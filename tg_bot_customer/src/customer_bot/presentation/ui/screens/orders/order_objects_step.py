from collections.abc import Sequence
from typing import Protocol

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderObjectCallback,
    OrderObjectsDoneCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _Item(Protocol):
    @property
    def display_name(self) -> str: ...

    @property
    def id(self) -> str: ...


class _View(Protocol):
    @property
    def max_count(self) -> int: ...

    @property
    def selected_count(self) -> int: ...

    @property
    def selected_ids(self) -> Sequence[str]: ...

    @property
    def items(self) -> Sequence[_Item]: ...

    @property
    def can_finish(self) -> bool: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        if self.data.max_count <= 1:
            return (
                "<b>Кого нужно взять в работу</b>\n\nВыберите карточку объекта ухода."
            )
        return (
            "<b>Кого нужно взять в работу</b>\n\n"
            f"Выберите до {self.data.max_count} карточек. Сейчас выбрано: {self.data.selected_count}."  # noqa: E501
        )

    def _build_keyboard(self) -> Markup:
        selected = set(self.data.selected_ids)
        keyboard = InlineKeyboardFactory()
        for index, item in enumerate(self.data.items):
            item_id = item.id
            marker = "✓ " if item_id in selected else ""
            keyboard.button(
                f"{marker}{item.display_name}",
                OrderObjectCallback(index=index),
            )
        if self.data.can_finish:
            keyboard.button("Готово", OrderObjectsDoneCallback())
        return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderOptionsDoneCallback,
    OrderOptionToggleCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _Item(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...


class _View(Protocol):
    @property
    def selected_count(self) -> int: ...

    @property
    def selected_ids(self) -> Sequence[str]: ...

    @property
    def items(self) -> Sequence[_Item]: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return (
            "<b>Дополнительные опции</b>\n\n"
            f"Выбрано: {self.data.selected_count}. Можно оставить без опций."
        )

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        selected = set(self.data.selected_ids)
        for item in self.data.items:
            item_id = item.id
            marker = "✓ " if item_id in selected else ""
            keyboard.button(
                f"{marker}{item.name}",
                OrderOptionToggleCallback(option_id=UUID(str(item.id))),
            )
        return (
            keyboard.button("Готово", OrderOptionsDoneCallback())
            .button(MsgKey.MAIN_MENU, MainMenuCallback())
            .as_markup()
        )

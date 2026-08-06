from collections.abc import Sequence
from html import escape
from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderResponsePerformerProfileCallback,
    OrderResponseRejectCallback,
    OrderResponseSelectCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.orders.status_labels import (
    response_status_label,
)
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _Item(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def performer_id(self) -> UUID: ...

    @property
    def status(self) -> str: ...


type _View = Sequence[_Item]


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        if not self.data:
            return "<b>Отклики</b>\n\nПока нет активных откликов по этому заказу."
        lines = ["<b>Отклики</b>"]
        for index, item in enumerate(self.data, start=1):
            lines.extend(
                (
                    "",
                    f"#{index}",
                    f"Исполнитель ID: {escape(str(item.performer_id))}",
                    f"Статус: {response_status_label(item.status)}",
                ),
            )
        return "\n".join(lines)

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory(row_width=3)
        for index, item in enumerate(self.data, start=1):
            match_id = item.id
            keyboard.button(
                f"Выбрать #{index}",
                OrderResponseSelectCallback(match_id=match_id),
            )
            keyboard.button(
                f"Отклонить #{index}",
                OrderResponseRejectCallback(match_id=match_id),
            )
            keyboard.button(
                "Открыть профиль",
                OrderResponsePerformerProfileCallback(
                    performer_id=item.performer_id,
                ),
            )
        return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()

from html import escape
from typing import Protocol
from uuid import UUID

from customer_bot.application.dto import OrderReportFileDTO
from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderComplaintOpenCallback,
    OrderLocationOpenCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import BaseScreen, Markup


class _View(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def order_id(self) -> UUID: ...

    @property
    def completed_work(self) -> str: ...

    @property
    def comment(self) -> str | None: ...

    @property
    def problem_flag(self) -> bool: ...

    @property
    def problem_description(self) -> str | None: ...

    @property
    def files(self) -> tuple[OrderReportFileDTO, ...]: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        lines = [
            "<b>Отчёт исполнителя</b>",
            "",
            f"Выполнено: {escape(self.data.completed_work)}",
        ]
        if self.data.comment:
            lines.extend(("", f"Комментарий: {escape(self.data.comment)}"))
        if self.data.problem_flag:
            lines.extend(("", "Исполнитель отметил проблему."))
            if self.data.problem_description:
                lines.append(escape(self.data.problem_description))
        if self.data.files:
            lines.extend(("", "Фотографии:"))
            for file in self.data.files:
                name = file.original_name or file.mime_type
                lines.append(f"• {escape(name)}: {escape(file.signed_url)}")
        return "\n".join(lines)

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        keyboard.button(
            "Открыть место",
            OrderLocationOpenCallback(order_id=self.data.order_id),
        )
        keyboard.button(
            "Подать жалобу",
            OrderComplaintOpenCallback(order_id=self.data.order_id),
        )
        return keyboard.button("Главное меню", MainMenuCallback()).as_markup()

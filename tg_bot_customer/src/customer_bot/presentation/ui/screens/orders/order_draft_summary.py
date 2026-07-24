from datetime import datetime
from html import escape
from typing import Protocol

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderDirectOpenCallback,
    OrderPublishPoolCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _View(Protocol):
    @property
    def service_name(self) -> str: ...

    @property
    def duration_minutes(self) -> int: ...

    @property
    def objects_count(self) -> int: ...

    @property
    def service_amount(self) -> object: ...

    @property
    def platform_fee_amount(self) -> object: ...

    @property
    def total_amount(self) -> object: ...

    @property
    def performers_count(self) -> int: ...

    @property
    def duration_unit(self) -> str: ...

    @property
    def start_at(self) -> datetime | None: ...

    @property
    def end_at(self) -> datetime | None: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        unit = {
            "days": "суток",
            "hours": "часов",
            "minutes": "минут",
        }.get(self.data.duration_unit, "минут")
        period = (
            f"{self.data.start_at.strftime('%d.%m.%Y %H:%M')} — "
            f"{self.data.end_at.strftime('%d.%m.%Y %H:%M')}"
            if self.data.start_at is not None and self.data.end_at is not None
            else None
        )
        duration_line = f"Длительность: {self.data.duration_minutes} {unit}."
        return "\n".join(
            (
                "<b>Проверьте заказ</b>",
                "",
                f"Услуга: {escape(self.data.service_name)}",
                duration_line,
                *((f"Период передачи и возврата: {escape(period)}",) if period else ()),
                f"Объектов: {self.data.objects_count}",
                "Опции: учтены в заказе",
                f"Услуга: {escape(str(self.data.service_amount))}",
                f"Комиссия: {escape(str(self.data.platform_fee_amount))}",
                f"Итого: {escape(str(self.data.total_amount))}",
                f"Подходящих исполнителей: {self.data.performers_count}",
                "",
                "Выберите способ публикации.",
            ),
        )

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        if self.data.performers_count:
            keyboard.button(MsgKey.PUBLISH_DIRECT, OrderDirectOpenCallback())
        keyboard.button(MsgKey.PUBLISH_POOL, OrderPublishPoolCallback())
        return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()

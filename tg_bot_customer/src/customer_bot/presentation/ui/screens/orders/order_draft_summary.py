from datetime import datetime
from html import escape
from typing import Protocol

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
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

    @property
    def location_label(self) -> str: ...


def duration_label(duration_minutes: int, duration_unit: str = "minutes") -> str:
    minutes = max(0, duration_minutes)
    if duration_unit == "days":
        units = max(1, (minutes + 24 * 60 - 1) // (24 * 60))
        return (
            f"{units} сутки"
            if units % 10 == 1 and units % 100 != 11
            else f"{units} суток"
        )
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours} ч. {remainder} мин."
    if hours:
        return f"{hours} ч."
    return f"{minutes} мин."


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        period = (
            f"{self.data.start_at.strftime('%d.%m.%Y %H:%M')} — "
            f"{self.data.end_at.strftime('%d.%m.%Y %H:%M')}"
            if self.data.start_at is not None and self.data.end_at is not None
            else None
        )
        duration_line = (
            "Длительность: "
            f"{duration_label(self.data.duration_minutes, self.data.duration_unit)}"
        )
        return "\n".join(
            (
                "<b>Проверьте заказ</b>",
                "",
                f"Услуга: {escape(self.data.service_name)}",
                duration_line,
                *((f"Период передачи и возврата: {escape(period)}",) if period else ()),
                f"Место: {escape(self.data.location_label)}",
                f"Объектов: {self.data.objects_count}",
                "Опции: учтены в заказе",
                "Расчёт: стоимость услуги + комиссия платформы",
                f"Услуга: {escape(str(self.data.service_amount))} ₽",
                f"Итого к оплате: {escape(str(self.data.total_amount))} ₽",
                f"Подходящих исполнителей: {self.data.performers_count}",
                "",
                "Выберите способ публикации.",
            ),
        )

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        keyboard.button(MsgKey.PUBLISH_POOL, OrderPublishPoolCallback())
        return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()

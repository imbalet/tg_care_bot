from collections.abc import Sequence
from datetime import datetime
from html import escape
from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderCardOpenCallback,
    OrdersPageCallback,
    SupportOpenCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.orders.status_labels import short_order_id
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey

CATEGORY_EMOJIS = {
    "nanny": "👶",
    "care": "🧓",
    "pet": "🐾",
}


def _order_status_label(status: str) -> str:
    return {
        "searching": "идет поиск",
        "waiting_payment": "ожидает оплаты",
        "confirmed": "подтвержден",
        "in_progress": "выполняется",
        "waiting_report": "ожидает отчет",
        "report_submitted": "отчет отправлен",
        "completed": "завершен",
        "cancelled": "отменен",
        "expired": "истек",
    }.get(status, escape(status))


def _datetime_label(value: datetime) -> str:
    return escape(value.strftime("%d.%m.%Y %H:%M"))


class MyOrderSummaryView(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def category_code(self) -> str: ...

    @property
    def category_name(self) -> str: ...

    @property
    def service_name(self) -> str: ...

    @property
    def status(self) -> str: ...

    @property
    def matching_mode(self) -> str | None: ...

    @property
    def total_amount(self) -> object: ...

    @property
    def start_at(self) -> datetime: ...

    @property
    def end_at(self) -> datetime: ...

    @property
    def objects_count(self) -> int: ...

    @property
    def payment_deadline_at(self) -> datetime | None: ...

    @property
    def matching_deadline_at(self) -> datetime: ...


class _View(Protocol):
    @property
    def items(self) -> Sequence[MyOrderSummaryView]: ...

    @property
    def page(self) -> int: ...

    @property
    def total_pages(self) -> int: ...

    @property
    def total_items(self) -> int: ...

    @property
    def group(self) -> str: ...

    @property
    def category_code(self) -> str | None: ...

    @property
    def active_category_code(self) -> str | None: ...

    @property
    def active_category_name(self) -> str | None: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        title = "Активные заказы" if self.data.group == "active" else "Архив заказов"
        if not self.data.items:
            return f"<b>{title}</b>\n\nЗдесь пока нет заказов."
        total_pages = self.data.total_pages or 1
        lines = [
            f"<b>{title}</b>",
            f"Страница {self.data.page} из {total_pages}. Всего: {self.data.total_items}.",  # noqa: E501
        ]
        for index, item in enumerate(self.data.items, start=1):
            lines.extend(
                (
                    "",
                    f"ID: {short_order_id(item.id)}",
                    f"{index}. {escape(item.service_name)}",
                    f"Направление: {escape(item.category_name)}",
                    f"Статус: {_order_status_label(item.status)}",
                    f"Время: {_datetime_label(item.start_at)}",
                    f"Итого: {escape(str(item.total_amount))} ₽",
                ),
            )
        return "\n".join(lines)

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        items = self.data.items
        page_number = self.data.page
        total_pages = self.data.total_pages
        for index, item in enumerate(items, start=1):
            order_id = item.id
            if order_id is not None:
                keyboard.button(
                    f"{index}. {item.service_name}",
                    OrderCardOpenCallback(
                        order_id=order_id,
                        group=self.data.group,
                        page=page_number,
                        category_code=self.data.category_code,
                    ),
                )
        if self.data.group != "active":
            keyboard.button(
                "Активные",
                OrdersPageCallback(
                    group="active", page=1, category_code=self.data.category_code
                ),
            )
        if self.data.group != "archive":
            keyboard.button(
                "Архив",
                OrdersPageCallback(
                    group="archive", page=1, category_code=self.data.category_code
                ),
            )
        if self.data.category_code is not None:
            keyboard.button(
                "Все направления",
                OrdersPageCallback(group=self.data.group, page=1),
            )
        elif self.data.active_category_code is not None:
            keyboard.button(
                "{} {}".format(
                    CATEGORY_EMOJIS.get(self.data.active_category_code, "📌"),
                    self.data.active_category_name or "Текущее направление",
                ),
                OrdersPageCallback(
                    group=self.data.group,
                    page=1,
                    category_code=self.data.active_category_code,
                ),
            )
        if page_number > 1:
            keyboard.button(
                "Назад",
                OrdersPageCallback(
                    group=self.data.group,
                    page=page_number - 1,
                    category_code=self.data.category_code,
                ),
            )
        if total_pages > page_number:
            keyboard.button(
                "Дальше",
                OrdersPageCallback(
                    group=self.data.group,
                    page=page_number + 1,
                    category_code=self.data.category_code,
                ),
            )
        return (
            keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback())
            .button("Поддержка", SupportOpenCallback())
            .as_markup()
        )

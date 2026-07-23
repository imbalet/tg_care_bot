from datetime import datetime
from html import escape
from typing import Protocol
from uuid import UUID

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderCancelPreviewCallback,
    OrderContactCallback,
    OrderDisputeOpenCallback,
    OrderLocationOpenCallback,
    OrderPerformerProfileCallback,
    OrderReportConfirmCallback,
    OrderReportOpenCallback,
    OrderResponsesOpenCallback,
    OrdersPageCallback,
    OrderStartConfirmCallback,
    PaymentRefreshCallback,
    SupportOpenCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


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


class _View(Protocol):
    @property
    def payment_status(self) -> str | None: ...

    @property
    def payment_expires_at(self) -> datetime | None: ...

    @property
    def id(self) -> UUID: ...

    @property
    def service_name(self) -> str: ...

    @property
    def group(self) -> str: ...

    @property
    def page(self) -> int: ...

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

    @property
    def payment_confirmation_url(self) -> str | None: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        lines = [
            "<b>Заказ</b>",
            "",
            f"Услуга: {escape(self.data.service_name)}",
            f"Статус: {_order_status_label(self.data.status)}",
            f"Начало: {_datetime_label(self.data.start_at)}",
            f"Окончание: {_datetime_label(self.data.end_at)}",
            f"Объектов: {self.data.objects_count}",
            f"Итого: {escape(str(self.data.total_amount))} ₽",
        ]
        if self.data.matching_mode is not None:
            lines.append(f"Подбор: {escape(self.data.matching_mode)}")
        if self.data.status == "searching":
            lines.append(
                f"Подбор до: {_datetime_label(self.data.matching_deadline_at)}"
            )
        if self.data.payment_deadline_at is not None:
            lines.append(
                f"Оплатить до: {_datetime_label(self.data.payment_deadline_at)}"
            )
        if self.data.payment_status is not None:
            lines.append(f"Платеж: {escape(self.data.payment_status)}")
        if self.data.status in {"confirmed", "in_progress", "waiting_report"}:
            lines.extend(
                (
                    "",
                    (
                        "Контакты и точный адрес будут доступны после "
                        "подтверждения заказа."
                    ),
                ),
            )
        return "\n".join(lines)

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        payment_url = self.data.payment_confirmation_url
        order_id = self.data.id
        status = self.data.status
        matching_mode = self.data.matching_mode
        if payment_url and payment_url.startswith("https://"):
            keyboard.url_button("Оплатить", payment_url)
        if status == "waiting_payment":
            keyboard.button(
                "Обновить оплату", PaymentRefreshCallback(order_id=order_id)
            )
            keyboard.button(
                "Отменить заказ",
                OrderCancelPreviewCallback(order_id=order_id),
            )
        if status == "searching" and matching_mode == "pool":
            keyboard.button("Отклики", OrderResponsesOpenCallback(order_id=order_id))
        if status in {
            "confirmed",
            "in_progress",
            "waiting_report",
            "report_submitted",
            "completed",
        }:
            keyboard.button(
                "Место оказания", OrderLocationOpenCallback(order_id=order_id)
            )
            keyboard.button(
                "Запросить контакт",
                OrderContactCallback(order_id=order_id),
            )
            keyboard.button(
                "Профиль исполнителя",
                OrderPerformerProfileCallback(order_id=order_id),
            )
        if status in {"report_submitted", "completed"}:
            keyboard.button("Отчёт", OrderReportOpenCallback(order_id=order_id))
            keyboard.button("Открыть спор", OrderDisputeOpenCallback(order_id=order_id))
        if status == "report_submitted":
            keyboard.button(
                "Подтвердить выполнение",
                OrderReportConfirmCallback(order_id=order_id),
            )
        if status == "confirmed":
            keyboard.button(
                "Подтвердить начало",
                OrderStartConfirmCallback(order_id=order_id),
            )
        return (
            keyboard.button(
                "К списку",
                OrdersPageCallback(group=self.data.group, page=self.data.page),
            )
            .button(MsgKey.MAIN_MENU, MainMenuCallback())
            .button("Поддержка", SupportOpenCallback())
            .as_markup()
        )

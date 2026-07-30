from datetime import UTC, datetime, timedelta
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
    PaymentRetryCallback,
    SupportOpenCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.orders.status_labels import (
    matching_mode_label,
    order_status_label,
    payment_status_label,
    short_order_id,
)
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


def _datetime_label(value: datetime) -> str:
    return escape(value.strftime("%d.%m.%Y %H:%M"))


def _duration_label(start_at: datetime, end_at: datetime) -> str:
    minutes = max(0, int((end_at - start_at).total_seconds() // 60))
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours} ч. {remainder} мин."
    if hours:
        return f"{hours} ч."
    return f"{minutes} мин."


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
    def category_name(self) -> str: ...

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

    @property
    def payment_attempts_used(self) -> int: ...

    @property
    def payment_max_attempts(self) -> int: ...

    @property
    def payment_retry_available(self) -> bool: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        lines = [
            "📦 <b>Заказ</b>",
            "",
            f"ID: {short_order_id(self.data.id)}",
            f"Услуга: {escape(self.data.service_name)}",
            f"Направление: {escape(self.data.category_name)}",
            "🔹 Статус: "
            f"{order_status_label(self.data.status, self.data.matching_mode)}",
            f"🗓 Начало: {_datetime_label(self.data.start_at)}",
            f"🗓 Окончание: {_datetime_label(self.data.end_at)}",
            f"⏱ Длительность: {_duration_label(self.data.start_at, self.data.end_at)}",
            f"Объектов: {self.data.objects_count}",
            f"Итого: {escape(str(self.data.total_amount))} ₽",
        ]
        if self.data.matching_mode is not None:
            lines.append(f"Подбор: {matching_mode_label(self.data.matching_mode)}")
        if self.data.status == "searching":
            lines.append(
                f"Подбор до: {_datetime_label(self.data.matching_deadline_at)}"
            )
        if self.data.payment_deadline_at is not None:
            lines.append(
                f"Оплатить до: {_datetime_label(self.data.payment_deadline_at)}"
            )
        if self.data.payment_status is not None:
            lines.append(f"Платеж: {payment_status_label(self.data.payment_status)}")
        if self.data.payment_status == "failed":
            lines.append(
                f"Попытки оплаты: {self.data.payment_attempts_used} "
                f"из {self.data.payment_max_attempts}"
            )
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
        if self.data.payment_status == "pending" and payment_url:
            keyboard.url_button("Оплатить", payment_url)
        if self.data.payment_status == "failed" and self.data.payment_retry_available:
            keyboard.button(
                "Повторить оплату",
                PaymentRetryCallback(order_id=order_id),
            )
        if status in {
            "searching",
            "waiting_payment",
            "confirmed",
            "in_progress",
            "waiting_report",
            "report_submitted",
        }:
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
        start_window_open = (
            datetime.now(UTC) >= (self.data.start_at - timedelta(minutes=30))
            and datetime.now(UTC) < self.data.end_at
        )
        if status == "confirmed" and start_window_open:
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

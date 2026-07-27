from html import escape
from uuid import UUID


def short_order_id(order_id: UUID | str) -> str:
    return f"#{str(order_id)[:8]}"


def order_status_label(status: str) -> str:
    return {
        "searching": "идёт поиск исполнителя",
        "waiting_payment": "ожидает оплаты",
        "confirmed": "подтверждён",
        "in_progress": "выполняется",
        "waiting_report": "ожидает отчёт",
        "report_submitted": "отчёт отправлен",
        "completed": "завершён",
        "cancelled": "отменён",
        "expired": "истёк",
    }.get(status, escape(status))


def payment_status_label(status: str) -> str:
    return {
        "pending": "ожидает оплаты",
        "succeeded": "оплачен",
        "failed": "ошибка оплаты",
        "expired": "срок оплаты истёк",
        "refunded": "возвращён",
    }.get(status, escape(status))


def matching_mode_label(mode: str) -> str:
    return {"pool": "общий подбор", "direct": "прямой заказ"}.get(
        mode,
        escape(mode),
    )

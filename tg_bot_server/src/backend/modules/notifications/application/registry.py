from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class NotificationAction:
    label: str
    callback_prefix: str

    def callback_data(self, entity_id: str | None) -> str | None:
        if entity_id is None:
            return None
        try:
            value = str(UUID(entity_id))
        except ValueError:
            return None
        return f"{self.callback_prefix}:{value}"


_ACTIONS: dict[str, tuple[NotificationAction, ...]] = {
    "direct_invitation_created": (
        NotificationAction("Принять", "direct_accept"),
        NotificationAction("Отклонить", "direct_reject"),
    ),
    "pool_response_created": (
        NotificationAction("Выбрать", "order_resp_select"),
        NotificationAction("Отклонить", "order_resp_reject"),
    ),
}

_OPEN_ORDER_TYPES = frozenset(
    {
        "direct_accepted",
        "direct_rejected",
        "direct_match_expired",
        "pool_response_rejected",
        "pool_response_selected",
        "pool_match_expired",
        "order_matching_expired",
        "pool_no_responses",
        "payment_success",
        "order_confirmed",
        "payment_expired_order_searching",
        "payment_expired_order_expired",
        "refund_requested",
        "refund_completed",
        "refund_failed",
        "order_approaching",
        "order_started",
        "order_finished",
        "report_submitted",
        "report_required",
        "report_overdue",
    }
)

_BODIES = {
    "direct_accepted": "Исполнитель принял приглашение. Заказ ожидает оплаты.",
    "direct_rejected": "Исполнитель отклонил приглашение.",
    "direct_invitation_created": "Вам поступило direct-приглашение.",
    "direct_match_expired": "Direct-приглашение истекло.",
    "pool_response_created": "Поступил новый отклик на заказ.",
    "pool_response_rejected": "Заказчик отклонил отклик.",
    "pool_response_selected": "Отклик выбран. Заказ ожидает оплаты.",
    "pool_match_expired": "Отклик истек.",
    "order_matching_expired": "Срок подбора истек. Заказ закрыт.",
    "pool_no_responses": "Подбор завершен: откликов исполнителей нет.",
    "payment_success": "Оплата подтверждена.",
    "order_confirmed": "Заказ подтвержден и закреплен за вами.",
    "payment_expired_order_searching": (
        "Оплата не поступила вовремя. Заказ вернулся в подбор."
    ),
    "payment_expired_order_expired": "Оплата не поступила вовремя. Заказ закрыт.",
    "refund_requested": "Запрошен возврат платежа.",
    "refund_completed": "Возврат платежа выполнен.",
    "refund_failed": "Возврат платежа не выполнен. Администратор разбирается.",
    "order_approaching": "Скоро начнется заказ.",
    "order_started": "Настало время заказа.",
    "order_finished": "Исполнитель завершил выполнение заказа.",
    "report_submitted": "Исполнитель отправил отчет по заказу.",
    "report_required": "Нужно отправить отчет по заказу.",
    "report_overdue": "Отчет по заказу просрочен.",
    "support_request_created": "Поступило новое обращение в поддержку.",
    "complaint_created": "Поступила новая жалоба.",
    "account_deletion_requested": "Поступил запрос на удаление аккаунта.",
}


def notification_actions(
    notification_type: str, entity_id: str | None
) -> list[list[dict[str, object]]] | None:
    actions = _ACTIONS.get(notification_type)
    if actions is None and notification_type in _OPEN_ORDER_TYPES:
        actions = (NotificationAction("Открыть заказ", "notification_order"),)
    if actions is None:
        return None
    buttons: list[dict[str, object]] = []
    for action in actions:
        callback_data = action.callback_data(entity_id)
        if callback_data is None:
            return None
        buttons.append({"text": action.label, "callback_data": callback_data})
    return [buttons]


def notification_action_entity_id(
    notification_type: str,
    payload: dict[str, object],
) -> str | None:
    if notification_type in {"direct_invitation_created", "pool_response_created"}:
        value = payload.get("match_id")
    else:
        value = payload.get("order_id")
    return value if isinstance(value, str) else None


def notification_body(notification_type: str) -> str:
    return _BODIES.get(notification_type, notification_type)

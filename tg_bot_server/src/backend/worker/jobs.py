from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from typing import Protocol
from uuid import UUID

import httpx
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.common.application import utc_now
from backend.common.infrastructure.database import for_update_skip_locked
from backend.modules.admin.infrastructure import AdminModel
from backend.modules.catalog.infrastructure import BusinessSettingModel
from backend.modules.customers.infrastructure import CustomerModel
from backend.modules.notifications.application import (
    notification_action_entity_id,
    notification_actions,
    notification_body,
)
from backend.modules.notifications.infrastructure import NotificationModel
from backend.modules.orders.infrastructure import (
    OrderAddressSnapshotModel,
    OrderMatchModel,
    OrderModel,
    OrderStatusHistoryModel,
)
from backend.modules.payments.infrastructure import PaymentModel
from backend.modules.performers.infrastructure import PerformerModel

_ADMIN_TABLE = AdminModel.__table__


class WorkerJob(Protocol):
    name: str

    async def run_once(self) -> None:
        pass


class WorkerLogger(Protocol):
    def warning(
        self,
        msg: object,
        *args: object,
        extra: Mapping[str, object] | None = None,
    ) -> None:
        pass

    def exception(
        self,
        msg: object,
        *args: object,
        extra: Mapping[str, object] | None = None,
    ) -> None:
        pass


class WorkerRunner(Protocol):
    def stop(self) -> None:
        pass

    async def run(self) -> None:
        pass

    async def run_once(self) -> None:
        pass


class NoopWorkerJob:
    name = "noop"

    async def run_once(self) -> None:
        return None


class NotificationWorkerJob:
    name = "notifications"

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        batch_limit: int,
        customer_bot_token: str,
        executor_bot_token: str,
        telegram_api_base_url: str,
        telegram_timeout_seconds: float,
        max_attempts: int = 3,
    ) -> None:
        self._session_factory = session_factory
        self._batch_limit = batch_limit
        self._customer_bot_token = customer_bot_token
        self._executor_bot_token = executor_bot_token
        self._telegram_api_base_url = telegram_api_base_url.rstrip("/")
        self._telegram_timeout_seconds = telegram_timeout_seconds
        self._max_attempts = max_attempts
        self._recovered_processing = False

    async def run_once(self) -> None:
        if not self._recovered_processing:
            await self._recover_processing()
            self._recovered_processing = True
        notification_ids = await self._claim_batch()
        for notification_id in notification_ids:
            try:
                delivery = await self._load_delivery(notification_id)
                await self._send_notification(delivery)
            except Exception as exc:
                await self._finish(notification_id, error=type(exc).__name__)
            else:
                await self._finish(notification_id)

    async def _recover_processing(self) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(NotificationModel)
                .where(
                    NotificationModel.channel == "telegram",
                    NotificationModel.status == "processing",
                )
                .values(status="pending", claimed_at=None),
            )
            await session.commit()

    async def _claim_batch(self) -> tuple[UUID, ...]:
        async with self._session_factory() as session:
            now = utc_now()
            result = await session.execute(
                for_update_skip_locked(
                    select(NotificationModel.id)
                    .where(
                        NotificationModel.channel == "telegram",
                        NotificationModel.status == "pending",
                        NotificationModel.scheduled_at <= now,
                        NotificationModel.attempts < self._max_attempts,
                    )
                    .order_by(NotificationModel.scheduled_at),
                    self._batch_limit,
                ),
            )
            notification_ids = tuple(result.scalars())
            if notification_ids:
                await session.execute(
                    update(NotificationModel)
                    .where(NotificationModel.id.in_(notification_ids))
                    .values(
                        status="processing",
                        attempts=NotificationModel.attempts + 1,
                        claimed_at=now,
                    ),
                )
            await session.commit()
            return notification_ids

    async def _load_delivery(self, notification_id: UUID) -> NotificationDelivery:
        async with self._session_factory() as session:
            notification = await session.get(NotificationModel, notification_id)
            if notification is None or notification.status != "processing":
                raise RuntimeError("Notification is not processing")
            token, chat_id = await self._telegram_target(session, notification)
            return NotificationDelivery(
                token=token,
                chat_id=chat_id,
                text=_notification_text(notification),
                reply_markup=_notification_keyboard(notification),
            )

    async def _finish(self, notification_id: UUID, error: str | None = None) -> None:
        async with self._session_factory() as session:
            notification = await session.get(NotificationModel, notification_id)
            if notification is None or notification.status != "processing":
                return
            if error is None:
                notification.status = "sent"
                notification.sent_at = utc_now()
                notification.claimed_at = None
                notification.last_error = None
            else:
                notification.last_error = error
                notification.claimed_at = None
                notification.status = (
                    "failed"
                    if notification.attempts >= self._max_attempts
                    else "pending"
                )
                notification.scheduled_at = utc_now()
            await session.commit()

    async def _send_notification(
        self,
        delivery: NotificationDelivery,
    ) -> None:
        async with httpx.AsyncClient(timeout=self._telegram_timeout_seconds) as client:
            response = await client.post(
                f"{self._telegram_api_base_url}/bot{delivery.token}/sendMessage",
                json={
                    "chat_id": delivery.chat_id,
                    "text": delivery.text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                    **(
                        {"reply_markup": delivery.reply_markup}
                        if delivery.reply_markup
                        else {}
                    ),
                },
            )
            response.raise_for_status()
        payload = response.json()
        if payload.get("ok") is not True:
            raise RuntimeError("Telegram sendMessage failed")

    async def _telegram_target(
        self,
        session: AsyncSession,
        notification: NotificationModel,
    ) -> tuple[str, int]:
        if notification.recipient_type == "customer":
            if not self._customer_bot_token:
                raise RuntimeError("Customer bot token is not configured")
            if notification.customer_id is None:
                raise RuntimeError("Notification customer is missing")
            result = await session.execute(
                select(CustomerModel.telegram_id).where(
                    CustomerModel.id == notification.customer_id,
                ),
            )
            telegram_id = result.scalar_one_or_none()
            if telegram_id is None:
                raise RuntimeError("Customer telegram id is missing")
            return self._customer_bot_token, int(telegram_id)
        if notification.recipient_type == "performer":
            if not self._executor_bot_token:
                raise RuntimeError("Executor bot token is not configured")
            if notification.performer_id is None:
                raise RuntimeError("Notification performer is missing")
            result = await session.execute(
                select(PerformerModel.telegram_id).where(
                    PerformerModel.id == notification.performer_id,
                ),
            )
            telegram_id = result.scalar_one_or_none()
            if telegram_id is None:
                raise RuntimeError("Performer telegram id is missing")
            return self._executor_bot_token, int(telegram_id)
        if notification.recipient_type == "performer_invitation":
            if not self._executor_bot_token:
                raise RuntimeError("Executor bot token is not configured")
            if notification.recipient_telegram_id is None:
                raise RuntimeError("Invitation recipient telegram id is missing")
            return self._executor_bot_token, int(notification.recipient_telegram_id)
        raise RuntimeError("Admin Telegram notifications are not configured")


@dataclass(frozen=True)
class NotificationDelivery:
    token: str
    chat_id: int
    text: str
    reply_markup: dict[str, object] | None


class DeadlinesWorkerJob:
    name = "deadlines"

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        batch_limit: int,
    ) -> None:
        self._session_factory = session_factory
        self._batch_limit = batch_limit

    async def run_once(self) -> None:
        async with self._session_factory() as session:
            now = utc_now()
            await self._expire_matches(
                session=session,
                now=now,
                source="direct",
                status="pending",
                reason="direct_response_deadline",
            )
            await self._expire_matches(
                session=session,
                now=now,
                source="pool",
                status="active",
                reason="pool_response_deadline",
            )
            await self._expire_searching_orders(session=session, now=now)
            await self._expire_waiting_payments(session=session, now=now)
            await self._process_execution_deadlines(session=session, now=now)
            await session.commit()

    async def _process_execution_deadlines(
        self,
        *,
        session: AsyncSession,
        now: datetime,
    ) -> None:
        approaching_minutes = await self._setting_int(
            session,
            "order_approaching_minutes",
            60,
        )
        report_deadline_minutes = await self._setting_int(
            session,
            "report_deadline_minutes",
            120,
        )
        result = await session.execute(
            for_update_skip_locked(
                select(OrderModel)
                .where(
                    OrderModel.status == "confirmed",
                    OrderModel.start_at <= now + timedelta(minutes=approaching_minutes),
                )
                .order_by(OrderModel.start_at),
                self._batch_limit,
            ),
        )
        for order in result.scalars():
            if order.start_at > now:
                await self._notify_once(
                    session=session,
                    recipient_type="customer",
                    customer_id=order.customer_id,
                    notification_type="order_approaching",
                    entity_id=order.id,
                    payload={"order_id": str(order.id)},
                    deduplication_key=f"order-approaching:{order.id}",
                )
            else:
                await self._notify_once(
                    session=session,
                    recipient_type="customer",
                    customer_id=order.customer_id,
                    notification_type="order_started",
                    entity_id=order.id,
                    payload={"order_id": str(order.id)},
                    deduplication_key=f"order-started:{order.id}",
                )
                await self._notify_once(
                    session=session,
                    recipient_type="performer",
                    performer_id=order.selected_performer_id,
                    notification_type="order_started",
                    entity_id=order.id,
                    payload={"order_id": str(order.id)},
                    deduplication_key=f"order-started:performer:{order.id}",
                )

        result = await session.execute(
            for_update_skip_locked(
                select(OrderModel)
                .where(
                    OrderModel.status == "in_progress",
                    OrderModel.end_at <= now,
                )
                .order_by(OrderModel.end_at),
                self._batch_limit,
            ),
        )
        for order_probe in result.scalars():
            order = await self._lock_order(session, order_probe.id)
            if order.status != "in_progress":
                continue
            order.status = "waiting_report"
            order.report_due_at = order.end_at + timedelta(
                minutes=report_deadline_minutes,
            )
            session.add(
                OrderStatusHistoryModel(
                    order_id=order.id,
                    from_status="in_progress",
                    to_status="waiting_report",
                    actor_type="system",
                    reason="planned_end",
                ),
            )
            await self._notify_once(
                session=session,
                recipient_type="performer",
                performer_id=order.selected_performer_id,
                notification_type="report_required",
                entity_id=order.id,
                payload={"order_id": str(order.id)},
                deduplication_key=f"report-required:{order.id}",
            )

        result = await session.execute(
            for_update_skip_locked(
                select(OrderModel)
                .where(
                    OrderModel.status == "waiting_report",
                    OrderModel.report_due_at <= now,
                )
                .order_by(OrderModel.report_due_at),
                self._batch_limit,
            ),
        )
        for order in result.scalars():
            order.requires_admin_attention = True
            await self._notify_once(
                session=session,
                recipient_type="performer",
                performer_id=order.selected_performer_id,
                notification_type="report_overdue",
                entity_id=order.id,
                payload={"order_id": str(order.id)},
                deduplication_key=f"report-overdue:performer:{order.id}",
            )
            admin_id = await self._first_admin_id(session)
            if admin_id is not None:
                await self._notify_once(
                    session=session,
                    recipient_type="admin",
                    admin_id=admin_id,
                    notification_type="report_overdue",
                    entity_id=order.id,
                    payload={"order_id": str(order.id)},
                    deduplication_key=f"report-overdue:admin:{order.id}",
                )

    async def _setting_int(
        self,
        session: AsyncSession,
        key: str,
        default: int,
    ) -> int:
        result = await session.execute(
            select(BusinessSettingModel.value).where(BusinessSettingModel.key == key),
        )
        value = result.scalar_one_or_none()
        return int(value) if value is not None else default

    async def _first_admin_id(self, session: AsyncSession) -> UUID | None:
        result = await session.execute(
            select(AdminModel.id).order_by(AdminModel.created_at).limit(1),
        )
        return result.scalar_one_or_none()

    async def _notify_once(
        self,
        *,
        session: AsyncSession,
        recipient_type: str,
        notification_type: str,
        entity_id: UUID,
        payload: dict[str, str],
        deduplication_key: str,
        customer_id: UUID | None = None,
        performer_id: UUID | None = None,
        admin_id: UUID | None = None,
    ) -> None:
        exists = await session.execute(
            select(NotificationModel.id).where(
                NotificationModel.deduplication_key == deduplication_key,
            ),
        )
        if exists.scalar_one_or_none() is not None:
            return
        now = utc_now()
        session.add(
            NotificationModel(
                recipient_type=recipient_type,
                customer_id=customer_id,
                performer_id=performer_id,
                admin_id=admin_id,
                channel="admin_panel" if recipient_type == "admin" else "telegram",
                type=notification_type,
                entity_type="order",
                entity_id=entity_id,
                payload=payload,
                deduplication_key=deduplication_key,
                status="sent" if recipient_type == "admin" else "pending",
                attempts=0,
                scheduled_at=now,
                sent_at=now if recipient_type == "admin" else None,
                delete_after=now + timedelta(days=30),
            ),
        )

    async def _expire_matches(
        self,
        *,
        session: AsyncSession,
        now: datetime,
        source: str,
        status: str,
        reason: str,
    ) -> None:
        result = await session.execute(
            for_update_skip_locked(
                select(OrderMatchModel)
                .where(
                    OrderMatchModel.source == source,
                    OrderMatchModel.status == status,
                    OrderMatchModel.response_expires_at <= now,
                )
                .order_by(OrderMatchModel.response_expires_at),
                self._batch_limit,
            ),
        )
        for match in result.scalars():
            match.status = "expired"
            match.closed_at = now
            match.close_reason = reason
            await self._cancel_pending_notifications(
                session=session,
                entity_type="order_match",
                entity_id=match.id,
            )
            self._add_notification(
                session=session,
                recipient_type="customer",
                customer_id=await self._order_customer_id(session, match.order_id),
                notification_type=f"{source}_match_expired",
                entity_type="order_match",
                entity_id=match.id,
                payload={"order_id": str(match.order_id), "match_id": str(match.id)},
                deduplication_key=f"{source}-match-expired:{match.id}",
            )

    async def _expire_searching_orders(
        self,
        *,
        session: AsyncSession,
        now: datetime,
    ) -> None:
        result = await session.execute(
            for_update_skip_locked(
                select(OrderModel)
                .where(
                    OrderModel.status == "searching",
                    OrderModel.matching_deadline_at <= now,
                )
                .order_by(OrderModel.matching_deadline_at),
                self._batch_limit,
            ),
        )
        for order in result.scalars():
            active_pool_responses = await session.scalar(
                select(func.count())
                .select_from(OrderMatchModel)
                .where(
                    OrderMatchModel.order_id == order.id,
                    OrderMatchModel.source == "pool",
                    OrderMatchModel.status == "active",
                ),
            )
            notification_type = (
                "pool_no_responses"
                if order.matching_mode == "pool" and not active_pool_responses
                else "order_matching_expired"
            )
            order.status = "expired"
            order.expired_reason = "matching_deadline"
            order.expired_at = now
            await self._cancel_pending_notifications(
                session=session,
                entity_type="order",
                entity_id=order.id,
            )
            self._add_notification(
                session=session,
                recipient_type="customer",
                customer_id=order.customer_id,
                notification_type=notification_type,
                entity_type="order",
                entity_id=order.id,
                payload={"order_id": str(order.id)},
                deduplication_key=f"{notification_type}:{order.id}",
            )

    async def _expire_waiting_payments(
        self,
        *,
        session: AsyncSession,
        now: datetime,
    ) -> None:
        result = await session.execute(
            for_update_skip_locked(
                select(OrderModel)
                .where(
                    OrderModel.status == "waiting_payment",
                    OrderModel.payment_deadline_at <= now,
                )
                .order_by(OrderModel.payment_deadline_at),
                self._batch_limit,
            ),
        )
        for order_probe in result.scalars():
            order = await self._lock_order(session, order_probe.id)
            payment = (
                await self._lock_payment(session, order.active_payment_id)
                if order.active_payment_id is not None
                else None
            )
            match = (
                await self._lock_match(session, order.selected_match_id)
                if order.selected_match_id is not None
                else None
            )
            if order.status != "waiting_payment":
                continue
            if payment is not None and payment.status in {"created", "pending"}:
                payment.status = "expired"
            await session.execute(
                delete(OrderAddressSnapshotModel).where(
                    OrderAddressSnapshotModel.order_id == order.id,
                ),
            )
            if match is not None and match.status == "selected":
                match.status = "expired"
                match.closed_at = now
                match.close_reason = "payment_deadline"
            from_status = order.status
            if order.matching_deadline_at > now:
                order.status = "searching"
                order.selected_performer_id = None
                order.selected_match_id = None
                order.active_payment_id = None
                order.payment_deadline_at = None
                if order.location_source == "performer_address":
                    order.address_id = None
                notification_type = "payment_expired_order_searching"
            else:
                order.status = "expired"
                order.expired_reason = "payment_deadline"
                order.expired_at = now
                notification_type = "payment_expired_order_expired"
            await self._cancel_pending_notifications(
                session=session,
                entity_type="order",
                entity_id=order.id,
            )
            self._add_notification(
                session=session,
                recipient_type="customer",
                customer_id=order.customer_id,
                notification_type=notification_type,
                entity_type="order",
                entity_id=order.id,
                payload={"order_id": str(order.id)},
                deduplication_key=f"{notification_type}:{order.id}",
            )
            session.add(
                OrderStatusHistoryModel(
                    order_id=order.id,
                    from_status=from_status,
                    to_status=order.status,
                    actor_type="system",
                    actor_id=None,
                    reason="payment_deadline",
                ),
            )

    async def _lock_order(
        self,
        session: AsyncSession,
        order_id: UUID,
    ) -> OrderModel:
        result = await session.execute(
            select(OrderModel).where(OrderModel.id == order_id).with_for_update(),
        )
        return result.scalar_one()

    async def _lock_payment(
        self,
        session: AsyncSession,
        payment_id: UUID,
    ) -> PaymentModel:
        result = await session.execute(
            select(PaymentModel).where(PaymentModel.id == payment_id).with_for_update(),
        )
        return result.scalar_one()

    async def _lock_match(
        self,
        session: AsyncSession,
        match_id: UUID,
    ) -> OrderMatchModel:
        result = await session.execute(
            select(OrderMatchModel)
            .where(OrderMatchModel.id == match_id)
            .with_for_update(),
        )
        return result.scalar_one()

    async def _order_customer_id(
        self,
        session: AsyncSession,
        order_id: UUID,
    ) -> UUID | None:
        result = await session.execute(
            select(OrderModel.customer_id).where(OrderModel.id == order_id),
        )
        return result.scalar_one_or_none()

    async def _cancel_pending_notifications(
        self,
        *,
        session: AsyncSession,
        entity_type: str,
        entity_id: UUID,
    ) -> None:
        await session.execute(
            update(NotificationModel)
            .where(
                NotificationModel.entity_type == entity_type,
                NotificationModel.entity_id == entity_id,
                NotificationModel.status == "pending",
            )
            .values(status="cancelled"),
        )

    def _add_notification(
        self,
        *,
        session: AsyncSession,
        recipient_type: str,
        notification_type: str,
        entity_type: str,
        entity_id: UUID,
        payload: dict[str, str],
        deduplication_key: str,
        customer_id: UUID | None = None,
        performer_id: UUID | None = None,
    ) -> None:
        if customer_id is None and performer_id is None:
            return
        now = utc_now()
        session.add(
            NotificationModel(
                recipient_type=recipient_type,
                customer_id=customer_id,
                performer_id=performer_id,
                admin_id=None,
                channel="telegram",
                type=notification_type,
                entity_type=entity_type,
                entity_id=entity_id,
                payload=payload,
                deduplication_key=deduplication_key,
                status="pending",
                attempts=0,
                scheduled_at=now,
                delete_after=now + timedelta(days=30),
            ),
        )


def _notification_text(notification: NotificationModel) -> str:
    if notification.type == "performer_invitation_created":
        return (
            "Вас пригласили зарегистрироваться исполнителем в We Are Close.\n"
            "Откройте бот исполнителя и отправьте /start."
        )
    title = _notification_title(notification)
    body = notification_body(notification.type)
    lines = [f"<b>{escape(title)}</b>", escape(body)]
    order_id = notification.payload.get("order_id")
    if order_id is not None:
        lines.append(f"Заказ: {escape(str(order_id))}")
    return "\n".join(lines)


def _notification_title(notification: NotificationModel) -> str:
    if notification.recipient_type == "customer":
        return "Заказчик"
    if notification.recipient_type == "performer":
        return "Исполнитель"
    return "Админ"


def _notification_keyboard(notification: NotificationModel) -> dict[str, object] | None:
    buttons = notification_actions(
        notification.type,
        notification_action_entity_id(notification.type, notification.payload),
    )
    return {"inline_keyboard": buttons} if buttons else None


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.1
    max_delay_seconds: float = 5.0

    def delay_for_attempt(self, attempt: int) -> float:
        delay = self.base_delay_seconds * (2 ** max(attempt - 1, 0))
        return float(min(delay, self.max_delay_seconds))


async def run_with_retry(
    operation: Callable[[], Awaitable[None]],
    policy: RetryPolicy,
    logger: WorkerLogger,
    operation_name: str,
) -> None:
    for attempt in range(1, policy.max_attempts + 1):
        try:
            await operation()
            return
        except Exception:
            if attempt >= policy.max_attempts:
                logger.exception(
                    "worker_operation_failed",
                    extra={
                        "operation_name": operation_name,
                        "attempt": attempt,
                        "max_attempts": policy.max_attempts,
                    },
                )
                raise
            delay = policy.delay_for_attempt(attempt)
            logger.warning(
                "worker_operation_retrying",
                extra={
                    "operation_name": operation_name,
                    "attempt": attempt,
                    "max_attempts": policy.max_attempts,
                    "delay_seconds": delay,
                },
            )
            await asyncio.sleep(delay)

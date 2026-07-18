import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from typing import Protocol
from uuid import UUID

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.common.application import utc_now
from backend.common.infrastructure.database import for_update_skip_locked
from backend.modules.admin.infrastructure import AdminModel
from backend.modules.customers.infrastructure import CustomerModel
from backend.modules.notifications.infrastructure import NotificationModel
from backend.modules.orders.infrastructure import (
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

    async def run_once(self) -> None:
        async with self._session_factory() as session:
            now = utc_now()
            result = await session.execute(
                for_update_skip_locked(
                    select(NotificationModel)
                    .where(
                        NotificationModel.status == "pending",
                        NotificationModel.scheduled_at <= now,
                        NotificationModel.attempts < self._max_attempts,
                    )
                    .order_by(NotificationModel.scheduled_at),
                    self._batch_limit,
                ),
            )
            notifications = tuple(result.scalars())
            for notification in notifications:
                notification.attempts += 1
                try:
                    await self._send_notification(session, notification)
                except Exception as exc:
                    notification.last_error = type(exc).__name__
                    if notification.attempts >= self._max_attempts:
                        notification.status = "failed"
                    continue
                else:
                    notification.status = "sent"
                    notification.sent_at = now
                    notification.last_error = None
            await session.commit()

    async def _send_notification(
        self,
        session: AsyncSession,
        notification: NotificationModel,
    ) -> None:
        token, chat_id = await self._telegram_target(session, notification)
        text = _notification_text(notification)
        async with httpx.AsyncClient(timeout=self._telegram_timeout_seconds) as client:
            response = await client.post(
                f"{self._telegram_api_base_url}/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
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
            await session.commit()

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
                notification_type="order_matching_expired",
                entity_type="order",
                entity_id=order.id,
                payload={"order_id": str(order.id)},
                deduplication_key=f"order-matching-expired:{order.id}",
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
    direction = (
        "Заказчик"
        if notification.recipient_type == "customer"
        else "Исполнитель"
        if notification.recipient_type == "performer"
        else "Админ"
    )
    lines = [
        f"<b>{escape(direction)}</b>",
        escape(notification.type),
    ]
    if notification.entity_type and notification.entity_id:
        lines.append(
            f"{escape(notification.entity_type)}: {escape(str(notification.entity_id))}"
        )
    order_id = notification.payload.get("order_id")
    if order_id is not None:
        lines.append(f"Заказ: {escape(str(order_id))}")
    return "\n".join(lines)


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

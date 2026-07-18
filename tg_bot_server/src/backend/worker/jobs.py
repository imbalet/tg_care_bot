import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.common.application import utc_now
from backend.common.infrastructure.database import for_update_skip_locked
from backend.modules.notifications.infrastructure import NotificationModel


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
        max_attempts: int = 3,
    ) -> None:
        self._session_factory = session_factory
        self._batch_limit = batch_limit
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
                notification.status = "sent"
                notification.sent_at = now
                notification.last_error = None
            await session.commit()


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

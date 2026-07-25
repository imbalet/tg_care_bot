from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.modules.catalog.infrastructure import CityModel
from backend.modules.notifications.infrastructure import NotificationModel
from backend.worker.jobs import NotificationWorkerJob


def _notification(*, key: str) -> NotificationModel:
    now = datetime.now(UTC)
    return NotificationModel(
        recipient_type="performer_invitation",
        recipient_telegram_id=900000001,
        channel="telegram",
        type="order_started",
        entity_type="order",
        entity_id=None,
        payload={"order_id": str(uuid4())},
        deduplication_key=key,
        status="pending",
        attempts=0,
        scheduled_at=now - timedelta(seconds=1),
        delete_after=now + timedelta(days=1),
    )


@pytest.mark.integration
async def test_business_change_and_outbox_row_share_transaction_boundary(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    rollback_city = CityModel(
        name="Rollback City",
        slug=f"rollback-{uuid4().hex}",
        timezone="Europe/Moscow",
    )
    rollback_notification = _notification(key=f"rollback-{uuid4().hex}")
    async with session_factory() as session:
        session.add_all((rollback_city, rollback_notification))
        await session.flush()
        await session.rollback()

    async with session_factory() as session:
        assert await session.get(CityModel, rollback_city.id) is None
        assert await session.get(NotificationModel, rollback_notification.id) is None

    committed_city = CityModel(
        name="Committed City",
        slug=f"committed-{uuid4().hex}",
        timezone="Europe/Moscow",
    )
    committed_notification = _notification(key=f"committed-{uuid4().hex}")
    async with session_factory() as session:
        session.add_all((committed_city, committed_notification))
        await session.commit()

    async with session_factory() as session:
        assert await session.get(CityModel, committed_city.id) is not None
        assert (
            await session.get(NotificationModel, committed_notification.id) is not None
        )
        await session.execute(
            delete(NotificationModel).where(
                NotificationModel.id == committed_notification.id,
            ),
        )
        await session.execute(
            delete(CityModel).where(CityModel.id == committed_city.id),
        )
        await session.commit()


@pytest.mark.integration
async def test_notification_worker_claims_a_row_only_once_concurrently(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    notification = _notification(key=f"concurrent-{uuid4().hex}")
    async with session_factory() as session:
        session.add(notification)
        await session.commit()

    first_worker = NotificationWorkerJob(
        session_factory=session_factory,
        batch_limit=10,
        customer_bot_token=str(uuid4()),
        executor_bot_token=str(uuid4()),
        telegram_api_base_url="http://mock-external:8080",
        telegram_timeout_seconds=1,
    )
    second_worker = NotificationWorkerJob(
        session_factory=session_factory,
        batch_limit=10,
        customer_bot_token=str(uuid4()),
        executor_bot_token=str(uuid4()),
        telegram_api_base_url="http://mock-external:8080",
        telegram_timeout_seconds=1,
    )

    claimed_batches = await asyncio.gather(
        first_worker._claim_batch(),
        second_worker._claim_batch(),
    )

    assert sorted(len(batch) for batch in claimed_batches) == [0, 1]
    assert sum(notification.id in batch for batch in claimed_batches) == 1

    async with session_factory() as session:
        stored = await session.get(NotificationModel, notification.id)
        assert stored is not None
        assert stored.status == "processing"
        assert stored.attempts == 1
        stored.status = "sent"
        await session.commit()

    async with session_factory() as session:
        await session.execute(
            delete(NotificationModel).where(
                NotificationModel.id == notification.id,
            ),
        )
        await session.commit()


@pytest.mark.integration
async def test_notification_worker_delivers_and_marks_success(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    notification = _notification(key=f"success-{uuid4().hex}")
    async with session_factory() as session:
        session.add(notification)
        await session.commit()

    worker = NotificationWorkerJob(
        session_factory=session_factory,
        batch_limit=10,
        customer_bot_token=str(uuid4()),
        executor_bot_token=str(uuid4()),
        telegram_api_base_url="http://mock-external:8080",
        telegram_timeout_seconds=1,
    )
    await worker.run_once()

    async with session_factory() as session:
        stored = await session.get(NotificationModel, notification.id)
        assert stored is not None
        assert stored.status == "sent"
        assert stored.attempts == 1
        assert stored.sent_at is not None
        assert stored.last_error is None
        await session.execute(
            delete(NotificationModel).where(
                NotificationModel.id == notification.id,
            ),
        )
        await session.commit()


@pytest.mark.integration
async def test_notification_worker_retries_then_marks_terminal_failure(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    notification = _notification(key=f"retry-{uuid4().hex}")
    async with session_factory() as session:
        session.add(notification)
        await session.commit()

    worker = NotificationWorkerJob(
        session_factory=session_factory,
        batch_limit=10,
        customer_bot_token=str(uuid4()),
        executor_bot_token=str(uuid4()),
        telegram_api_base_url="http://mock-external:8080",
        telegram_timeout_seconds=1,
        max_attempts=2,
    )

    for expected_status in ("pending", "failed"):
        claimed = await worker._claim_batch()
        assert claimed == (notification.id,)
        await worker._finish(notification.id, error="RuntimeError")
        async with session_factory() as session:
            stored = await session.get(NotificationModel, notification.id)
            assert stored is not None
            assert stored.status == expected_status
            assert stored.attempts in {1, 2}
            assert stored.last_error == "RuntimeError"

    async with session_factory() as session:
        stored = await session.get(NotificationModel, notification.id)
        assert stored is not None
        assert stored.status == "failed"
        assert stored.attempts == 2
        await session.execute(
            delete(NotificationModel).where(
                NotificationModel.id == notification.id,
            ),
        )
        await session.commit()

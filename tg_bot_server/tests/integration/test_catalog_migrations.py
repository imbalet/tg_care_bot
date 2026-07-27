from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.catalog.infrastructure import CityModel
from backend.modules.catalog.infrastructure.persistence.queries import (
    SqlAlchemyCatalogQueryService,
)
from backend.modules.notifications.infrastructure import NotificationModel
from backend.worker.jobs import NotificationWorkerJob


@pytest.mark.integration
async def test_migrations_provide_catalog_seed(session: AsyncSession) -> None:
    city_count = await session.scalar(select(func.count()).select_from(CityModel))

    assert city_count == 1


@pytest.mark.integration
async def test_integration_services_are_reachable(
    redis: Redis,
    s3_client: Any,
) -> None:
    assert await redis.ping()
    assert s3_client.list_buckets()["Buckets"]


@pytest.mark.integration
async def test_catalog_query_service_returns_seeded_active_cities(
    session: AsyncSession,
) -> None:
    cities = await SqlAlchemyCatalogQueryService(session).list_cities(active_only=True)

    assert len(cities) == 1
    assert cities[0].name == "Ростов-на-Дону"
    assert cities[0].slug == "rostov-on-don"


@pytest.mark.integration
async def test_session_transaction_can_be_rolled_back(session: AsyncSession) -> None:
    from tests.support.builders import CatalogBuilder

    city = CatalogBuilder().city()
    session.add(city)
    await session.flush()
    await session.rollback()

    assert await session.get(CityModel, city.id) is None


@pytest.mark.integration
async def test_notification_claim_and_terminal_failure_are_persisted(
    session_factory: Any,
) -> None:
    now = datetime.now(UTC)
    notification = NotificationModel(
        recipient_type="performer_invitation",
        recipient_telegram_id=900000001,
        channel="telegram",
        type="order_started",
        entity_type="order",
        entity_id=None,
        payload={"order_id": "test"},
        deduplication_key=f"integration-notification-{now.timestamp()}",
        status="pending",
        attempts=0,
        scheduled_at=now - timedelta(seconds=1),
        delete_after=now + timedelta(days=1),
    )
    async with session_factory() as setup_session:
        setup_session.add(notification)
        await setup_session.commit()

    worker = NotificationWorkerJob(
        session_factory=session_factory,
        batch_limit=10,
        customer_bot_token=str(uuid4()),
        executor_bot_token=str(uuid4()),
        telegram_api_base_url="http://mock-external:8080",
        telegram_timeout_seconds=1,
        max_attempts=1,
    )
    claimed = await worker._claim_batch()
    assert claimed == (notification.id,)
    await worker._finish(notification.id, error="RuntimeError")

    async with session_factory() as check_session:
        stored = await check_session.get(NotificationModel, notification.id)
        assert stored is not None
        assert stored.status == "failed"
        assert stored.last_error == "RuntimeError"
        await check_session.execute(
            delete(NotificationModel).where(NotificationModel.id == notification.id),
        )
        await check_session.commit()

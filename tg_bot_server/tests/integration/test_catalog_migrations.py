from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.catalog.infrastructure import CityModel
from backend.modules.catalog.infrastructure.persistence.queries import (
    SqlAlchemyCatalogQueryService,
)


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
    assert cities[0].slug == "moscow"


@pytest.mark.integration
async def test_session_transaction_can_be_rolled_back(session: AsyncSession) -> None:
    from tests.support.builders import CatalogBuilder

    city = CatalogBuilder().city()
    session.add(city)
    await session.flush()
    await session.rollback()

    assert await session.get(CityModel, city.id) is None

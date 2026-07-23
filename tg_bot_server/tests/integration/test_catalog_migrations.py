from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.catalog.infrastructure import CityModel


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

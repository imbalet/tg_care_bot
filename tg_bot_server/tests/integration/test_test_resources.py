from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.catalog.infrastructure import CityModel


@pytest.mark.integration
async def test_database_transaction_is_rolled_back_between_tests(
    session: AsyncSession,
) -> None:
    city = await session.scalar(select(CityModel).limit(1))
    assert city is not None
    city.name = "transaction-local-name"
    await session.flush()


@pytest.mark.integration
async def test_redis_and_s3_are_isolated_resources(
    redis: Redis,
    s3_client: Any,
    session: AsyncSession,
) -> None:
    city = await session.scalar(select(CityModel).limit(1))
    assert city is not None
    assert city.name != "transaction-local-name"
    await redis.set("test-resource-key", "value")
    assert await redis.get("test-resource-key") == "value"
    s3_client.put_object(
        Bucket=s3_client.list_buckets()["Buckets"][0]["Name"],
        Key="test-resource-key",
        Body=b"value",
        ContentType="text/plain",
    )
    assert s3_client.list_buckets()["Buckets"]

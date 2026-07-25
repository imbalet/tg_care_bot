from __future__ import annotations

from collections.abc import AsyncIterator, Generator, Iterator
from contextlib import suppress
from typing import Any

import boto3
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from backend.bootstrap.settings import get_settings
from backend.common.infrastructure.database import create_engine, create_session_factory
from backend.common.infrastructure.redis import create_redis_client
from tests.support.database import IntegrationDatabase
from tests.support.settings import apply_test_environment


@pytest.fixture(scope="session")
def integration_database(worker_id: str) -> Generator[IntegrationDatabase]:
    database = IntegrationDatabase(worker_id=worker_id)
    database.setup()
    yield database
    database.cleanup()


@pytest.fixture(scope="session", autouse=True)
def integration_environment(
    integration_database: IntegrationDatabase,
) -> Iterator[None]:
    monkeypatch = pytest.MonkeyPatch()
    apply_test_environment(
        monkeypatch,
        {
            "DB_HOST": integration_database.settings.db_host,
            "DB_PORT": str(integration_database.settings.db_port),
            "DB_NAME": integration_database.database_name,
            "DB_USER": integration_database.settings.db_user,
            "DB_PASS": integration_database.settings.db_pass,
            "REDIS_DB": str(_redis_database_number(integration_database.worker_id)),
            "S3_BUCKET": f"we-are-close-test-{integration_database.worker_id}",
        },
        preserve_existing=True,
    )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    monkeypatch.undo()


@pytest_asyncio.fixture
async def engine(
    integration_database: IntegrationDatabase,
) -> AsyncIterator[AsyncEngine]:
    del integration_database
    test_engine = create_engine(get_settings().database_url)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest_asyncio.fixture
async def session(
    engine: AsyncEngine,
) -> AsyncIterator[AsyncSession]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        test_session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield test_session
        finally:
            await test_session.close()
            await transaction.rollback()


@pytest_asyncio.fixture
async def redis(integration_database: IntegrationDatabase) -> AsyncIterator[Redis]:
    del integration_database
    client = create_redis_client(get_settings().redis_url)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
def s3_client() -> Iterator[Any]:
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
    )
    bucket = settings.s3_bucket
    with suppress(client.exceptions.BucketAlreadyOwnedByYou):
        client.create_bucket(Bucket=bucket)
    try:
        yield client
    finally:
        objects = client.list_objects_v2(Bucket=bucket).get("Contents", [])
        if objects:
            client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": item["Key"]} for item in objects]},
            )
        client.delete_bucket(Bucket=bucket)


def _redis_database_number(worker_id: str) -> int:
    if worker_id == "master":
        return 0
    digits = "".join(character for character in worker_id if character.isdigit())
    return (int(digits or "0") + 1) % 16

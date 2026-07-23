from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from backend.common.infrastructure import S3ObjectStorage
from backend.common.infrastructure.database import create_engine, create_session_factory
from backend.common.infrastructure.redis import create_redis_client
from backend.modules.geo.infrastructure import DaDataGeocoder

from .settings import Settings


def create_database_engine(settings: Settings) -> AsyncEngine:
    return create_engine(settings.database_url)


def create_database_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


def create_redis(settings: Settings) -> Redis:
    return create_redis_client(settings.redis_url)


def create_storage(settings: Settings) -> S3ObjectStorage:
    return S3ObjectStorage(
        endpoint_url=settings.s3_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
        bucket=settings.s3_bucket,
        region=settings.s3_region,
        signed_url_ttl_seconds=settings.s3_signed_url_ttl_seconds,
    )


def create_geocoder(settings: Settings) -> DaDataGeocoder:
    return DaDataGeocoder(
        api_key=settings.dadata_api_key,
        secret_key=settings.dadata_secret_key,
        base_url=settings.dadata_base_url,
        timeout_seconds=settings.dadata_timeout_seconds,
        retry_count=settings.dadata_retry_count,
    )

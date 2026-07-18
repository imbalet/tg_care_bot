from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from backend.common.infrastructure.database import create_engine, create_session_factory
from backend.common.infrastructure.redis import create_redis_client

from .settings import Settings


def create_database_engine(settings: Settings) -> AsyncEngine:
    return create_engine(settings.database_url)


def create_database_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


def create_redis(settings: Settings) -> Redis:
    return create_redis_client(settings.redis_url)

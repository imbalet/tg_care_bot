from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from backend.bootstrap.settings import Settings
from backend.common.infrastructure.database import create_engine, create_session_factory
from backend.common.infrastructure.redis import create_redis_client


@dataclass(frozen=True)
class Container:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    redis: Redis

    async def close(self) -> None:
        await self.redis.aclose()
        await self.engine.dispose()


def create_container(settings: Settings) -> Container:
    engine = create_engine(settings.database_url)
    return Container(
        settings=settings,
        engine=engine,
        session_factory=create_session_factory(engine),
        redis=create_redis_client(settings.redis_url),
    )

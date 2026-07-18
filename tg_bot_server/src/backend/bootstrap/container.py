from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from backend.bootstrap.resources import (
    create_database_engine,
    create_database_session_factory,
    create_redis,
)
from backend.bootstrap.settings import Settings


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
    engine = create_database_engine(settings)
    return Container(
        settings=settings,
        engine=engine,
        session_factory=create_database_session_factory(engine),
        redis=create_redis(settings),
    )

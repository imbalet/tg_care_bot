from dataclasses import dataclass
from typing import TYPE_CHECKING

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

if TYPE_CHECKING:
    from backend.bootstrap.services import ApplicationServices

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

    def services(self) -> ApplicationServices:
        from backend.bootstrap.services import ApplicationServices

        return ApplicationServices(self)

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

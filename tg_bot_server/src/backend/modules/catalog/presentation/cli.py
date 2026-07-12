import argparse
import asyncio

from backend.bootstrap.container import create_container
from backend.bootstrap.settings import get_settings
from backend.modules.catalog.application import SeedMvpCatalogUseCase


async def seed_mvp_catalog() -> None:
    settings = get_settings()
    container = create_container(settings)
    try:
        async with container.session_factory() as session:
            await SeedMvpCatalogUseCase(session).execute()
            await session.commit()
    finally:
        await container.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed MVP catalog.")
    parser.parse_args()
    asyncio.run(seed_mvp_catalog())


if __name__ == "__main__":
    main()


__all__ = ["main", "seed_mvp_catalog"]

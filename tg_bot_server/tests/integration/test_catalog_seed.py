import os

import pytest
from sqlalchemy import func, select

from backend.bootstrap.settings import get_settings
from backend.common.infrastructure.database import create_engine, create_session_factory
from backend.modules.catalog.application import SeedMvpCatalogUseCase
from backend.modules.catalog.infrastructure import (
    BusinessSettingModel,
    CityModel,
    LegalDocumentModel,
    ObjectCountMultiplierModel,
    ServiceCategoryModel,
    ServiceModel,
)
from tests.integration.database import IntegrationDatabase, migrate_to_head

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="PostgreSQL integration tests require RUN_POSTGRES_TESTS=1",
)


@pytest.mark.asyncio
async def test_mvp_catalog_seed_is_idempotent() -> None:
    get_settings.cache_clear()
    database = IntegrationDatabase()
    database.apply_to_environment()
    migrate_to_head(database)
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            await SeedMvpCatalogUseCase(session).execute()
            await SeedMvpCatalogUseCase(session).execute()
            await session.commit()

        async with session_factory() as session:
            city_count = await session.scalar(
                select(func.count()).select_from(CityModel),
            )
            category_count = await session.scalar(
                select(func.count()).select_from(ServiceCategoryModel),
            )
            service_count = await session.scalar(
                select(func.count()).select_from(ServiceModel),
            )
            multiplier_count = await session.scalar(
                select(func.count()).select_from(ObjectCountMultiplierModel),
            )
            setting_count = await session.scalar(
                select(func.count()).select_from(BusinessSettingModel),
            )
            document_count = await session.scalar(
                select(func.count()).select_from(LegalDocumentModel),
            )
        assert city_count == 1
        assert category_count == 3
        assert service_count == 6
        assert multiplier_count == 6
        assert setting_count == 22
        assert document_count == 4
    finally:
        await engine.dispose()
        get_settings.cache_clear()

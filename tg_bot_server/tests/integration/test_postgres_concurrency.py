import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.modules.catalog.infrastructure import CityModel


@pytest.mark.integration
async def test_for_update_serializes_competing_transactions(
    engine: AsyncEngine,
) -> None:
    async with engine.connect() as first, engine.connect() as second:
        first_transaction = await first.begin()
        second_transaction = await second.begin()
        try:
            await first.execute(
                select(CityModel.id).limit(1).with_for_update(),
            )

            blocked = asyncio.create_task(
                second.execute(select(CityModel.id).limit(1).with_for_update()),
            )
            await asyncio.sleep(0.05)
            assert not blocked.done()

            await first_transaction.rollback()
            await asyncio.wait_for(blocked, timeout=2)
        finally:
            if not blocked.done():
                blocked.cancel()
                await blocked
            await second_transaction.rollback()

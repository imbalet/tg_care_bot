from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.catalog.infrastructure.persistence.models import (
    BusinessSettingModel,
)


class SqlAlchemyBusinessSettingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_key(self, key: str) -> BusinessSettingModel | None:
        result = await self._session.execute(
            select(BusinessSettingModel).where(BusinessSettingModel.key == key),
        )
        return result.scalar_one_or_none()

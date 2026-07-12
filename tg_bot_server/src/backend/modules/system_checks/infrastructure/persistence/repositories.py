from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.system_checks.domain import SystemCheckRecord
from backend.modules.system_checks.infrastructure.persistence.models import (
    SystemCheckRecordModel,
)


class SqlAlchemySystemCheckRecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: SystemCheckRecord) -> None:
        self._session.add(
            SystemCheckRecordModel(
                id=record.id,
                name=record.name,
                created_at=record.created_at,
            ),
        )


__all__ = ["SqlAlchemySystemCheckRecordRepository"]

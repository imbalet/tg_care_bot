from typing import Protocol

from backend.modules.system_checks.domain import SystemCheckRecord


class SystemCheckRecordRepository(Protocol):
    async def add(self, record: SystemCheckRecord) -> None:
        pass


__all__ = ["SystemCheckRecordRepository"]

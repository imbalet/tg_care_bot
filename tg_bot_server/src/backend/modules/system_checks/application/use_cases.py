from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from backend.common.infrastructure.database import SqlAlchemyUnitOfWork
from backend.modules.system_checks.application.dto import SystemCheckRecordDTO
from backend.modules.system_checks.domain import SystemCheckRecord


@dataclass(frozen=True)
class CreateSystemCheckCommand:
    name: str


class CreateSystemCheckUseCase:
    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: CreateSystemCheckCommand) -> SystemCheckRecordDTO:
        from backend.modules.system_checks.infrastructure import (
            SqlAlchemySystemCheckRecordRepository,
        )

        record = SystemCheckRecord(
            id=uuid4(),
            name=command.name,
            created_at=datetime.now(UTC),
        )
        async with self._uow as uow:
            repository = SqlAlchemySystemCheckRecordRepository(uow.session)
            await repository.add(record)
            await uow.commit()
        return SystemCheckRecordDTO(
            id=record.id,
            name=record.name,
            created_at=record.created_at,
        )


__all__ = ["CreateSystemCheckCommand", "CreateSystemCheckUseCase"]

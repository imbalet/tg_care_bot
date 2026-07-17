from dataclasses import dataclass

from backend.common.application import Clock, SystemClock, new_uuid
from backend.common.infrastructure.database import SqlAlchemyUnitOfWork
from backend.modules.system_checks.application.dto import SystemCheckRecordDTO
from backend.modules.system_checks.domain import SystemCheckRecord


@dataclass(frozen=True)
class CreateSystemCheckCommand:
    name: str


class CreateSystemCheckUseCase:
    def __init__(
        self,
        uow: SqlAlchemyUnitOfWork,
        clock: Clock | None = None,
    ) -> None:
        self._uow = uow
        self._clock = clock or SystemClock()

    async def execute(self, command: CreateSystemCheckCommand) -> SystemCheckRecordDTO:
        from backend.modules.system_checks.infrastructure import (
            SqlAlchemySystemCheckRecordRepository,
        )

        record = SystemCheckRecord(
            id=new_uuid(),
            name=command.name,
            created_at=self._clock.now(),
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

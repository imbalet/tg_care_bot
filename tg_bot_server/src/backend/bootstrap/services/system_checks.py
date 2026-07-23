from ._shared import (
    Any,
    CreateSystemCheckCommand,
    CreateSystemCheckUseCase,
)
from .context import Service


class SystemCheckServices(Service):
    async def create_system_check(self, command: CreateSystemCheckCommand) -> Any:
        return await CreateSystemCheckUseCase(self._uow()).execute(command)

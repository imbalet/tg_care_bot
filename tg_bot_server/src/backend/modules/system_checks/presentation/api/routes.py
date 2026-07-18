from typing import Annotated

from fastapi import APIRouter, Depends

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.infrastructure.database import SqlAlchemyUnitOfWork
from backend.common.presentation import require_service_key
from backend.modules.system_checks.application import (
    CreateSystemCheckCommand,
    CreateSystemCheckUseCase,
)

from .mappers import system_check_response
from .schemas import CreateSystemCheckRequest, SystemCheckResponse

router = APIRouter(
    prefix="/internal/system-checks",
    tags=["system-checks"],
    dependencies=[Depends(require_service_key)],
)


@router.post("", status_code=201)
async def create_system_check(
    request: CreateSystemCheckRequest,
    container: Annotated[Container, Depends(get_container)],
) -> SystemCheckResponse:
    use_case = CreateSystemCheckUseCase(
        SqlAlchemyUnitOfWork(container.session_factory),
    )
    record = await use_case.execute(CreateSystemCheckCommand(name=request.name))
    return system_check_response(record)

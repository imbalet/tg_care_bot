from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.infrastructure.database import SqlAlchemyUnitOfWork
from backend.common.presentation import require_service_key
from backend.modules.system_checks.application import (
    CreateSystemCheckCommand,
    CreateSystemCheckUseCase,
)

router = APIRouter(
    prefix="/internal/system-checks",
    tags=["system-checks"],
    dependencies=[Depends(require_service_key)],
)


class CreateSystemCheckRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SystemCheckResponse(BaseModel):
    id: str
    name: str
    created_at: str


@router.post("", status_code=201)
async def create_system_check(
    request: CreateSystemCheckRequest,
    container: Annotated[Container, Depends(get_container)],
) -> SystemCheckResponse:
    use_case = CreateSystemCheckUseCase(
        SqlAlchemyUnitOfWork(container.session_factory),
    )
    record = await use_case.execute(CreateSystemCheckCommand(name=request.name))
    return SystemCheckResponse(
        id=str(record.id),
        name=record.name,
        created_at=record.created_at.isoformat(),
    )

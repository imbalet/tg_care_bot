from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key

router = APIRouter()


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, str | dict[str, str]]:
    dependencies: dict[str, str] = {}
    async with container.session_factory() as session:
        await session.execute(text("select 1"))
        dependencies["postgres"] = "ok"
    await container.redis.ping()
    dependencies["redis"] = "ok"
    return {"status": "ok", "dependencies": dependencies}


@router.get("/internal/ping", dependencies=[Depends(require_service_key)])
async def internal_ping() -> dict[str, str]:
    return {"status": "ok"}

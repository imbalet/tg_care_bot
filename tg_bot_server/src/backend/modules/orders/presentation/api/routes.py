from typing import Annotated

from fastapi import APIRouter, Depends

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key
from backend.modules.availability.infrastructure import SqlAlchemyAvailabilityRepository
from backend.modules.orders.application import (
    CalculatePricePreviewCommand,
    CalculatePricePreviewUseCase,
    CreateDirectOrderUseCase,
    CreatePoolOrderUseCase,
)
from backend.modules.orders.infrastructure import (
    SqlAlchemyOrderRepository,
    SqlAlchemyPricingRepository,
)

from .mappers import (
    create_direct_command,
    create_pool_command,
    order_response,
    price_preview_response,
)
from .schemas import (
    DirectOrderRequest,
    OrderRequest,
    OrderResponse,
    PricePreviewRequest,
    PricePreviewResponse,
)

router = APIRouter(
    prefix="/api/orders",
    tags=["orders"],
    dependencies=[Depends(require_service_key)],
)


@router.post("/pool", status_code=201)
async def create_pool(
    request: OrderRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderResponse:
    async with container.session_factory() as session:
        order = await CreatePoolOrderUseCase(
            SqlAlchemyOrderRepository(session),
            SqlAlchemyPricingRepository(session),
        ).execute(create_pool_command(request))
        await session.commit()
    return order_response(order)


@router.post("/direct", status_code=201)
async def create_direct(
    request: DirectOrderRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderResponse:
    async with container.session_factory() as session:
        order = await CreateDirectOrderUseCase(
            SqlAlchemyOrderRepository(session),
            SqlAlchemyPricingRepository(session),
            SqlAlchemyAvailabilityRepository(session),
        ).execute(create_direct_command(request))
        await session.commit()
    return order_response(order)


@router.post("/price-preview")
async def price_preview(
    request: PricePreviewRequest,
    container: Annotated[Container, Depends(get_container)],
) -> PricePreviewResponse:
    async with container.session_factory() as session:
        preview = await CalculatePricePreviewUseCase(
            SqlAlchemyPricingRepository(session),
        ).execute(
            CalculatePricePreviewCommand(
                service_id=request.service_id,
                start_at=request.start_at,
                end_at=request.end_at,
                objects_count=request.objects_count,
            ),
        )
    return price_preview_response(preview)

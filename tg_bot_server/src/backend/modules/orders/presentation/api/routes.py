from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key
from backend.modules.orders.application import (
    CalculatePricePreviewCommand,
)

from .mappers import (
    create_direct_command,
    create_pool_command,
    match_action_response,
    match_response,
    order_response,
    price_preview_response,
)
from .schemas import (
    CustomerMatchActionRequest,
    DirectOrderRequest,
    MatchActionResponse,
    OrderMatchResponse,
    OrderRequest,
    OrderResponse,
    PerformerMatchActionRequest,
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
    order = await container.services().create_pool_order(create_pool_command(request))
    return order_response(order)


@router.post("/direct", status_code=201)
async def create_direct(
    request: DirectOrderRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderResponse:
    order = await container.services().create_direct_order(
        create_direct_command(request),
    )
    return order_response(order)


@router.post("/price-preview")
async def price_preview(
    request: PricePreviewRequest,
    container: Annotated[Container, Depends(get_container)],
) -> PricePreviewResponse:
    preview = await container.services().calculate_price_preview(
        CalculatePricePreviewCommand(
            service_id=request.service_id,
            start_at=request.start_at,
            end_at=request.end_at,
            objects_count=request.objects_count,
        ),
    )
    return price_preview_response(preview)


@router.get("/available")
async def list_available_pool_orders(
    performer_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    limit: int = 20,
) -> list[OrderResponse]:
    orders = await container.services().list_available_pool_orders(
        performer_id=performer_id,
        limit=limit,
    )
    return [order_response(order) for order in orders]


@router.post("/{order_id}/pool-responses", status_code=201)
async def create_pool_response(
    order_id: UUID,
    request: PerformerMatchActionRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderMatchResponse:
    match = await container.services().create_pool_response(
        order_id=order_id,
        performer_id=request.performer_id,
    )
    return match_response(match)


@router.get("/{order_id}/matches")
async def list_order_matches(
    order_id: UUID,
    customer_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> list[OrderMatchResponse]:
    matches = await container.services().list_order_matches(
        order_id=order_id,
        customer_id=customer_id,
    )
    return [match_response(match) for match in matches]


@router.post("/matches/{match_id}/direct/accept")
async def accept_direct_match(
    match_id: UUID,
    request: PerformerMatchActionRequest,
    container: Annotated[Container, Depends(get_container)],
) -> MatchActionResponse:
    result = await container.services().accept_direct_match(
        match_id=match_id,
        performer_id=request.performer_id,
    )
    return match_action_response(result)


@router.post("/matches/{match_id}/direct/reject")
async def reject_direct_match(
    match_id: UUID,
    request: PerformerMatchActionRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderMatchResponse:
    match = await container.services().reject_direct_match(
        match_id=match_id,
        performer_id=request.performer_id,
    )
    return match_response(match)


@router.post("/matches/{match_id}/pool/select")
async def select_pool_response(
    match_id: UUID,
    request: CustomerMatchActionRequest,
    container: Annotated[Container, Depends(get_container)],
) -> MatchActionResponse:
    result = await container.services().select_pool_response(
        match_id=match_id,
        customer_id=request.customer_id,
    )
    return match_action_response(result)


@router.post("/matches/{match_id}/pool/reject")
async def reject_pool_response(
    match_id: UUID,
    request: CustomerMatchActionRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderMatchResponse:
    match = await container.services().reject_pool_response(
        match_id=match_id,
        customer_id=request.customer_id,
    )
    return match_response(match)

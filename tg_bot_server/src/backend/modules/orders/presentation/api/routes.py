from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.domain import NotFoundError
from backend.common.presentation import require_service_key
from backend.modules.orders.application import (
    CalculatePricePreviewCommand,
)

from .mappers import (
    cancellation_preview_response,
    create_direct_command,
    create_pool_command,
    match_action_response,
    match_response,
    my_order_card_response,
    my_orders_page_response,
    order_location_response,
    order_response,
    price_preview_response,
    report_detail_response,
    report_response,
)
from .schemas import (
    CancellationPreviewResponse,
    CancelOrderRequest,
    CustomerDirectPerformerRequest,
    CustomerMatchActionRequest,
    DirectOrderRequest,
    MatchActionResponse,
    MyOrderCardResponse,
    MyOrdersPageResponse,
    OrderLocationResponse,
    OrderMatchResponse,
    OrderReportDetailResponse,
    OrderReportRequest,
    OrderReportResponse,
    OrderRequest,
    OrderResponse,
    PerformerMatchActionRequest,
    PerformerOrderActionRequest,
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
    order = await container.orders.create_pool_order(create_pool_command(request))
    return order_response(order)


@router.post("/direct", status_code=201)
async def create_direct(
    request: DirectOrderRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderResponse:
    order = await container.orders.create_direct_order(
        create_direct_command(request),
    )
    return order_response(order)


@router.post("/price-preview")
async def price_preview(
    request: PricePreviewRequest,
    container: Annotated[Container, Depends(get_container)],
) -> PricePreviewResponse:
    preview = await container.orders.calculate_price_preview(
        CalculatePricePreviewCommand(
            customer_id=request.customer_id,
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
    orders = await container.orders.list_available_pool_orders(
        performer_id=performer_id,
        limit=limit,
    )
    return [order_response(order) for order in orders]


@router.get("/customer/{customer_id}/my")
async def list_customer_my_orders(
    customer_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    group: Annotated[str, Query(pattern="^(active|archive)$")] = "active",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=10)] = 5,
    category_code: str | None = None,
) -> MyOrdersPageResponse:
    orders = await container.orders.list_customer_my_orders(
        customer_id=customer_id,
        group=group,
        page=page,
        page_size=page_size,
        category_code=category_code,
    )
    return my_orders_page_response(orders)


@router.get("/customer/{customer_id}/my/{order_id}")
async def get_customer_my_order(
    customer_id: UUID,
    order_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> MyOrderCardResponse:
    order = await container.orders.get_customer_my_order(
        customer_id=customer_id,
        order_id=order_id,
    )
    if order is None:
        raise NotFoundError("Order not found")
    return my_order_card_response(order)


@router.get(
    "/customer/{customer_id}/my/{order_id}/cancellation-preview",
)
async def get_customer_cancellation_preview(
    customer_id: UUID,
    order_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> CancellationPreviewResponse:
    preview = await container.orders.get_customer_cancellation_preview(
        customer_id=customer_id,
        order_id=order_id,
    )
    if preview is None:
        raise NotFoundError("Order not found")
    return cancellation_preview_response(preview)


@router.get("/customer/{customer_id}/my/{order_id}/location")
async def get_customer_order_location(
    customer_id: UUID,
    order_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> OrderLocationResponse:
    location = await container.orders.get_customer_order_location(
        customer_id=customer_id,
        order_id=order_id,
    )
    if location is None:
        raise NotFoundError("Order location not found")
    return order_location_response(location)


@router.post("/customer/{customer_id}/my/{order_id}/confirm-report")
async def confirm_customer_report(
    customer_id: UUID,
    order_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> OrderResponse:
    order = await container.orders.confirm_customer_report(
        order_id=order_id,
        customer_id=customer_id,
    )
    return order_response(order)


@router.get("/performer/{performer_id}/my")
async def list_performer_my_orders(
    performer_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    group: Annotated[str, Query(pattern="^(active|archive)$")] = "active",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=10)] = 5,
) -> MyOrdersPageResponse:
    orders = await container.orders.list_performer_my_orders(
        performer_id=performer_id,
        group=group,
        page=page,
        page_size=page_size,
    )
    return my_orders_page_response(orders)


@router.get("/performer/{performer_id}/my/{order_id}")
async def get_performer_my_order(
    performer_id: UUID,
    order_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> MyOrderCardResponse:
    order = await container.orders.get_performer_my_order(
        performer_id=performer_id,
        order_id=order_id,
    )
    if order is None:
        raise NotFoundError("Order not found")
    return my_order_card_response(order)


@router.get("/performer/{performer_id}/my/{order_id}/location")
async def get_performer_order_location(
    performer_id: UUID,
    order_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> OrderLocationResponse:
    location = await container.orders.get_performer_order_location(
        performer_id=performer_id,
        order_id=order_id,
    )
    if location is None:
        raise NotFoundError("Order location not found")
    return order_location_response(location)


@router.post("/{order_id}/pool-responses", status_code=201)
async def create_pool_response(
    order_id: UUID,
    request: PerformerMatchActionRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderMatchResponse:
    match = await container.orders.create_pool_response(
        order_id=order_id,
        performer_id=request.performer_id,
    )
    return match_response(match)


@router.post("/{order_id}/direct/performer", status_code=201)
async def invite_direct_performer(
    order_id: UUID,
    request: CustomerDirectPerformerRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderMatchResponse:
    match = await container.orders.invite_direct_performer(
        order_id=order_id,
        customer_id=request.customer_id,
        performer_id=request.performer_id,
    )
    return match_response(match)


@router.post("/{order_id}/publish-pool")
async def publish_pool_order(
    order_id: UUID,
    request: CustomerMatchActionRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderResponse:
    order = await container.orders.publish_pool_order(
        order_id=order_id,
        customer_id=request.customer_id,
    )
    return order_response(order)


@router.get("/{order_id}/matches")
async def list_order_matches(
    order_id: UUID,
    customer_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> list[OrderMatchResponse]:
    matches = await container.orders.list_order_matches(
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
    result = await container.orders.accept_direct_match(
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
    match = await container.orders.reject_direct_match(
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
    result = await container.orders.select_pool_response(
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
    match = await container.orders.reject_pool_response(
        match_id=match_id,
        customer_id=request.customer_id,
    )
    return match_response(match)


@router.post("/{order_id}/start")
async def start_order(
    order_id: UUID,
    request: PerformerOrderActionRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderResponse:
    order = await container.orders.start_order(
        order_id=order_id,
        performer_id=request.performer_id,
    )
    return order_response(order)


@router.post("/{order_id}/finish")
async def finish_order(
    order_id: UUID,
    request: PerformerOrderActionRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderResponse:
    order = await container.orders.finish_order(
        order_id=order_id,
        performer_id=request.performer_id,
    )
    return order_response(order)


@router.post("/{order_id}/report")
async def submit_order_report(
    order_id: UUID,
    request: OrderReportRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderReportResponse:
    report = await container.orders.submit_order_report(
        order_id=order_id,
        performer_id=request.performer_id,
        completed_work=request.completed_work,
        comment=request.comment,
        problem_flag=request.problem_flag,
        problem_description=request.problem_description,
        file_ids=tuple(request.file_ids),
    )
    return report_response(report)


@router.get("/customer/{customer_id}/my/{order_id}/report")
async def get_customer_order_report(
    customer_id: UUID,
    order_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> OrderReportDetailResponse:
    report = await container.orders.get_order_report(
        order_id=order_id,
        customer_id=customer_id,
    )
    if report is None:
        raise NotFoundError("Order report not found")
    return report_detail_response(report)


@router.get("/performer/{performer_id}/my/{order_id}/report")
async def get_performer_order_report(
    performer_id: UUID,
    order_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> OrderReportDetailResponse:
    report = await container.orders.get_order_report(
        order_id=order_id,
        performer_id=performer_id,
    )
    if report is None:
        raise NotFoundError("Order report not found")
    return report_detail_response(report)


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: UUID,
    request: CancelOrderRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderResponse:
    order = await container.orders.cancel_order(
        order_id=order_id,
        actor_type=request.actor_type,
        actor_id=request.actor_id,
    )
    return order_response(order)

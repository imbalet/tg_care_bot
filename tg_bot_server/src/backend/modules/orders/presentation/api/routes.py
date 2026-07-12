from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key
from backend.modules.orders.application import (
    CalculatePricePreviewCommand,
    CalculatePricePreviewUseCase,
    CancelDraftOrderUseCase,
    CreateDraftOrderCommand,
    CreateDraftOrderUseCase,
    OrderDTO,
    PricePreviewDTO,
    PublishDirectOrderCommand,
    PublishDirectOrderUseCase,
    PublishPoolOrderUseCase,
    UpdateDraftOrderCommand,
    UpdateDraftOrderUseCase,
)
from backend.modules.orders.infrastructure import (
    SqlAlchemyOrderRepository,
    SqlAlchemyPricingRepository,
)

router = APIRouter(
    prefix="/api/orders",
    tags=["orders"],
    dependencies=[Depends(require_service_key)],
)


class PricePreviewRequest(BaseModel):
    service_id: UUID
    start_at: datetime
    end_at: datetime
    objects_count: int = Field(ge=1)


class DraftOrderRequest(BaseModel):
    customer_id: UUID
    service_id: UUID
    start_at: datetime
    end_at: datetime
    care_object_ids: list[UUID] = Field(min_length=1)
    address_id: UUID | None = None
    customer_comment: str | None = Field(default=None, max_length=2000)
    report_photo_consent: bool | None = None
    option_values: dict[UUID, Any] = Field(default_factory=dict)


class PublishDirectRequest(BaseModel):
    performer_id: UUID


class OrderResponse(BaseModel):
    id: str
    customer_id: str | None
    service_id: str
    service_code: str
    service_name: str
    schedule_policy: str
    photo_policy: str | None
    matching_mode: str | None
    status: str
    address_id: str | None
    location_source: str
    start_at: str
    end_at: str
    objects_count: int
    total_amount: Decimal
    performer_amount: Decimal
    platform_fee_amount: Decimal
    matching_deadline_at: str


class PricePreviewResponse(BaseModel):
    service_id: str
    service_code: str
    service_name: str
    price_type: str
    duration_minutes: int
    billable_minutes: int | None
    started_24h_units: int | None
    objects_count: int
    object_multiplier: Decimal
    base_price: Decimal
    service_amount: Decimal
    platform_fee_percent: Decimal
    platform_fee_amount: Decimal
    performer_amount: Decimal
    total_amount: Decimal
    hold_limit_checked: bool


@router.post("/drafts", status_code=201)
async def create_draft(
    request: DraftOrderRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderResponse:
    async with container.session_factory() as session:
        order = await CreateDraftOrderUseCase(
            SqlAlchemyOrderRepository(session),
            SqlAlchemyPricingRepository(session),
        ).execute(_create_draft_command(request))
        await session.commit()
    return _order_response(order)


@router.put("/drafts/{order_id}")
async def update_draft(
    order_id: UUID,
    request: DraftOrderRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderResponse:
    async with container.session_factory() as session:
        order = await UpdateDraftOrderUseCase(
            SqlAlchemyOrderRepository(session),
            SqlAlchemyPricingRepository(session),
        ).execute(_update_draft_command(order_id, request))
        await session.commit()
    return _order_response(order)


@router.post("/drafts/{order_id}/cancel")
async def cancel_draft(
    order_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> OrderResponse:
    async with container.session_factory() as session:
        order = await CancelDraftOrderUseCase(
            SqlAlchemyOrderRepository(session),
        ).execute(order_id)
        await session.commit()
    return _order_response(order)


@router.post("/drafts/{order_id}/publish-pool")
async def publish_pool(
    order_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> OrderResponse:
    async with container.session_factory() as session:
        order = await PublishPoolOrderUseCase(
            SqlAlchemyOrderRepository(session),
        ).execute(order_id)
        await session.commit()
    return _order_response(order)


@router.post("/drafts/{order_id}/publish-direct")
async def publish_direct(
    order_id: UUID,
    request: PublishDirectRequest,
    container: Annotated[Container, Depends(get_container)],
) -> OrderResponse:
    async with container.session_factory() as session:
        order = await PublishDirectOrderUseCase(
            SqlAlchemyOrderRepository(session),
            SqlAlchemyPricingRepository(session),
        ).execute(
            PublishDirectOrderCommand(
                order_id=order_id,
                performer_id=request.performer_id,
            ),
        )
        await session.commit()
    return _order_response(order)


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
    return _price_preview_response(preview)


def _create_draft_command(request: DraftOrderRequest) -> CreateDraftOrderCommand:
    return CreateDraftOrderCommand(
        customer_id=request.customer_id,
        service_id=request.service_id,
        start_at=request.start_at,
        end_at=request.end_at,
        care_object_ids=tuple(request.care_object_ids),
        address_id=request.address_id,
        customer_comment=request.customer_comment,
        report_photo_consent=request.report_photo_consent,
        option_values=request.option_values,
    )


def _update_draft_command(
    order_id: UUID,
    request: DraftOrderRequest,
) -> UpdateDraftOrderCommand:
    return UpdateDraftOrderCommand(
        order_id=order_id,
        customer_id=request.customer_id,
        service_id=request.service_id,
        start_at=request.start_at,
        end_at=request.end_at,
        care_object_ids=tuple(request.care_object_ids),
        address_id=request.address_id,
        customer_comment=request.customer_comment,
        report_photo_consent=request.report_photo_consent,
        option_values=request.option_values,
    )


def _order_response(order: OrderDTO) -> OrderResponse:
    return OrderResponse(
        id=str(order.id),
        customer_id=str(order.customer_id) if order.customer_id is not None else None,
        service_id=str(order.service_id),
        service_code=order.service_code,
        service_name=order.service_name,
        schedule_policy=order.schedule_policy,
        photo_policy=order.photo_policy,
        matching_mode=order.matching_mode,
        status=order.status,
        address_id=str(order.address_id) if order.address_id is not None else None,
        location_source=order.location_source,
        start_at=order.start_at.isoformat(),
        end_at=order.end_at.isoformat(),
        objects_count=order.objects_count,
        total_amount=order.total_amount,
        performer_amount=order.performer_amount,
        platform_fee_amount=order.platform_fee_amount,
        matching_deadline_at=order.matching_deadline_at.isoformat(),
    )


def _price_preview_response(preview: PricePreviewDTO) -> PricePreviewResponse:
    return PricePreviewResponse(
        service_id=str(preview.service_id),
        service_code=preview.service_code,
        service_name=preview.service_name,
        price_type=preview.price_type,
        duration_minutes=preview.duration_minutes,
        billable_minutes=preview.billable_minutes,
        started_24h_units=preview.started_24h_units,
        objects_count=preview.objects_count,
        object_multiplier=preview.object_multiplier,
        base_price=preview.base_price,
        service_amount=preview.service_amount,
        platform_fee_percent=preview.platform_fee_percent,
        platform_fee_amount=preview.platform_fee_amount,
        performer_amount=preview.performer_amount,
        total_amount=preview.total_amount,
        hold_limit_checked=preview.hold_limit_checked,
    )


__all__ = ["router"]

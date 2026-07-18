from backend.modules.orders.application import (
    CreateDirectOrderCommand,
    CreatePoolOrderCommand,
    OrderDTO,
    PricePreviewDTO,
)

from .schemas import (
    DirectOrderRequest,
    OrderRequest,
    OrderResponse,
    PricePreviewResponse,
)


def create_pool_command(request: OrderRequest) -> CreatePoolOrderCommand:
    return CreatePoolOrderCommand(
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


def create_direct_command(request: DirectOrderRequest) -> CreateDirectOrderCommand:
    return CreateDirectOrderCommand(
        performer_id=request.performer_id,
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


def order_response(order: OrderDTO) -> OrderResponse:
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


def price_preview_response(preview: PricePreviewDTO) -> PricePreviewResponse:
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

from backend.modules.orders.application import (
    CreateDirectOrderCommand,
    CreatePoolOrderCommand,
    MatchActionDTO,
    OrderDTO,
    OrderMatchDTO,
    PaymentPromptDTO,
    PricePreviewDTO,
)

from .schemas import (
    DirectOrderRequest,
    MatchActionResponse,
    OrderMatchResponse,
    OrderRequest,
    OrderResponse,
    PaymentPromptResponse,
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


def match_response(match: OrderMatchDTO) -> OrderMatchResponse:
    return OrderMatchResponse(
        id=str(match.id),
        order_id=str(match.order_id),
        performer_id=str(match.performer_id),
        source=match.source,
        status=match.status,
        starts_at=match.starts_at.isoformat(),
        ends_at=match.ends_at.isoformat(),
        response_expires_at=match.response_expires_at.isoformat(),
        selected_at=match.selected_at.isoformat()
        if match.selected_at is not None
        else None,
        closed_at=match.closed_at.isoformat() if match.closed_at is not None else None,
        close_reason=match.close_reason,
    )


def payment_prompt_response(payment: PaymentPromptDTO) -> PaymentPromptResponse:
    return PaymentPromptResponse(
        payment_id=str(payment.payment_id),
        confirmation_url=payment.confirmation_url,
        expires_at=payment.expires_at.isoformat(),
    )


def match_action_response(result: MatchActionDTO) -> MatchActionResponse:
    return MatchActionResponse(
        order=order_response(result.order),
        match=match_response(result.match),
        payment=payment_prompt_response(result.payment)
        if result.payment is not None
        else None,
    )

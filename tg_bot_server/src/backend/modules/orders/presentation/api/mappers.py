from backend.common.application import to_timezone
from backend.modules.orders.application import (
    CancellationPreviewDTO,
    CreateDirectOrderCommand,
    CreatePoolOrderCommand,
    MatchActionDTO,
    MyOrderCardDTO,
    MyOrdersPageDTO,
    MyOrderSummaryDTO,
    OrderDTO,
    OrderLocationDTO,
    OrderMatchDTO,
    OrderReportDetailDTO,
    OrderReportDTO,
    PaymentPromptDTO,
    PricePreviewDTO,
)

from .schemas import (
    CancellationPreviewResponse,
    DirectOrderRequest,
    FullAddressSnapshotResponse,
    MatchActionResponse,
    MyOrderCardResponse,
    MyOrdersPageResponse,
    MyOrderSummaryResponse,
    OrderLocationResponse,
    OrderMatchResponse,
    OrderReportDetailResponse,
    OrderReportFileResponse,
    OrderReportResponse,
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
        location_source=request.location_source,
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
        location_source=request.location_source,
        customer_comment=request.customer_comment,
        report_photo_consent=request.report_photo_consent,
        option_values=request.option_values,
    )


def order_response(order: OrderDTO) -> OrderResponse:
    start_at = to_timezone(order.start_at, order.timezone)
    end_at = to_timezone(order.end_at, order.timezone)
    matching_deadline_at = to_timezone(order.matching_deadline_at, order.timezone)
    return OrderResponse(
        id=str(order.id),
        customer_id=str(order.customer_id) if order.customer_id is not None else None,
        service_id=str(order.service_id),
        service_code=order.service_code,
        service_name=order.service_name,
        price_type=order.price_type,
        schedule_policy=order.schedule_policy,
        photo_policy=order.photo_policy,
        matching_mode=order.matching_mode,
        status=order.status,
        address_id=str(order.address_id) if order.address_id is not None else None,
        location_source=order.location_source,
        start_at=start_at.isoformat(),
        end_at=end_at.isoformat(),
        objects_count=order.objects_count,
        total_amount=order.total_amount,
        performer_amount=order.performer_amount,
        platform_fee_amount=order.platform_fee_amount,
        matching_deadline_at=matching_deadline_at.isoformat(),
        timezone=order.timezone,
        distance_km=order.distance_km,
    )


def order_location_response(location: OrderLocationDTO) -> OrderLocationResponse:
    address = location.address
    return OrderLocationResponse(
        order_id=str(location.order_id),
        city_name=location.city_name,
        district_name=location.district_name,
        address=(
            FullAddressSnapshotResponse(
                city_name=address.city_name,
                district_name=address.district_name,
                address_text=address.address_text,
                fias_id=address.fias_id,
                latitude=address.latitude,
                longitude=address.longitude,
                geocoding_provider=address.geocoding_provider,
                geocoding_quality=address.geocoding_quality,
                entrance=address.entrance,
                floor=address.floor,
                apartment=address.apartment,
                comment=address.comment,
            )
            if address is not None
            else None
        ),
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


def cancellation_preview_response(
    preview: CancellationPreviewDTO,
) -> CancellationPreviewResponse:
    return CancellationPreviewResponse(
        order_id=str(preview.order_id),
        order_status=preview.order_status,
        can_cancel=preview.can_cancel,
        refund_outcome=preview.refund_outcome,
        refund_amount=preview.refund_amount,
        policy_version=preview.policy_version,
        partial_refund_percent=preview.partial_refund_percent,
        remaining_minutes=preview.remaining_minutes,
    )


def match_response(match: OrderMatchDTO) -> OrderMatchResponse:
    starts_at = to_timezone(match.starts_at, match.timezone)
    ends_at = to_timezone(match.ends_at, match.timezone)
    response_expires_at = to_timezone(match.response_expires_at, match.timezone)
    selected_at = (
        to_timezone(match.selected_at, match.timezone)
        if match.selected_at is not None
        else None
    )
    closed_at = (
        to_timezone(match.closed_at, match.timezone)
        if match.closed_at is not None
        else None
    )
    return OrderMatchResponse(
        id=str(match.id),
        order_id=str(match.order_id),
        performer_id=str(match.performer_id),
        source=match.source,
        status=match.status,
        starts_at=starts_at.isoformat(),
        ends_at=ends_at.isoformat(),
        response_expires_at=response_expires_at.isoformat(),
        selected_at=selected_at.isoformat() if selected_at is not None else None,
        closed_at=closed_at.isoformat() if closed_at is not None else None,
        close_reason=match.close_reason,
        timezone=match.timezone,
        service_name=match.service_name,
        total_amount=match.total_amount,
        distance_km=match.distance_km,
        customer_comment=match.customer_comment,
    )


def report_response(report: OrderReportDTO) -> OrderReportResponse:
    return OrderReportResponse(
        id=str(report.id),
        order_id=str(report.order_id),
        performer_id=str(report.performer_id),
        completed_work=report.completed_work,
        comment=report.comment,
        problem_flag=report.problem_flag,
        problem_description=report.problem_description,
        submitted_at=report.submitted_at.isoformat(),
        file_ids=[str(file_id) for file_id in report.file_ids],
    )


def report_detail_response(report: OrderReportDetailDTO) -> OrderReportDetailResponse:
    return OrderReportDetailResponse(
        id=str(report.id),
        order_id=str(report.order_id),
        performer_id=str(report.performer_id),
        completed_work=report.completed_work,
        comment=report.comment,
        problem_flag=report.problem_flag,
        problem_description=report.problem_description,
        submitted_at=report.submitted_at.isoformat(),
        files=[
            OrderReportFileResponse(
                id=str(file.id),
                original_name=file.original_name,
                mime_type=file.mime_type,
                signed_url=file.signed_url,
            )
            for file in report.files
        ],
    )


def payment_prompt_response(payment: PaymentPromptDTO) -> PaymentPromptResponse:
    expires_at = to_timezone(payment.expires_at, payment.timezone)
    return PaymentPromptResponse(
        payment_id=str(payment.payment_id),
        confirmation_url=payment.confirmation_url,
        expires_at=expires_at.isoformat(),
        timezone=payment.timezone,
    )


def match_action_response(result: MatchActionDTO) -> MatchActionResponse:
    return MatchActionResponse(
        order=order_response(result.order),
        match=match_response(result.match),
        payment=payment_prompt_response(result.payment)
        if result.payment is not None
        else None,
    )


def my_order_summary_response(order: MyOrderSummaryDTO) -> MyOrderSummaryResponse:
    start_at = to_timezone(order.start_at, order.timezone)
    end_at = to_timezone(order.end_at, order.timezone)
    payment_deadline_at = (
        to_timezone(order.payment_deadline_at, order.timezone)
        if order.payment_deadline_at is not None
        else None
    )
    matching_deadline_at = to_timezone(order.matching_deadline_at, order.timezone)
    return MyOrderSummaryResponse(
        id=str(order.id),
        category_code=order.category_code,
        service_name=order.service_name,
        price_type=order.price_type,
        matching_mode=order.matching_mode,
        status=order.status,
        start_at=start_at.isoformat(),
        end_at=end_at.isoformat(),
        objects_count=order.objects_count,
        total_amount=order.total_amount,
        payment_deadline_at=payment_deadline_at.isoformat()
        if payment_deadline_at is not None
        else None,
        matching_deadline_at=matching_deadline_at.isoformat(),
        timezone=order.timezone,
    )


def my_order_card_response(order: MyOrderCardDTO) -> MyOrderCardResponse:
    summary = my_order_summary_response(order)
    payment_expires_at = (
        to_timezone(order.payment_expires_at, order.timezone)
        if order.payment_expires_at is not None
        else None
    )
    return MyOrderCardResponse(
        **summary.model_dump(),
        payment_status=order.payment_status,
        payment_confirmation_url=order.payment_confirmation_url,
        payment_expires_at=payment_expires_at.isoformat()
        if payment_expires_at is not None
        else None,
        payment_attempts_used=order.payment_attempts_used,
        payment_max_attempts=order.payment_max_attempts,
        payment_retry_available=order.payment_retry_available,
        customer_comment=order.customer_comment,
    )


def my_orders_page_response(page: MyOrdersPageDTO) -> MyOrdersPageResponse:
    return MyOrdersPageResponse(
        items=[my_order_summary_response(order) for order in page.items],
        page=page.page,
        page_size=page.page_size,
        total_items=page.total_items,
        total_pages=page.total_pages,
    )

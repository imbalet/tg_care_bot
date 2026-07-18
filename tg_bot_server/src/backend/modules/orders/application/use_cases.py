from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from backend.common.domain import NotFoundError, ValidationError
from backend.modules.availability.application import AvailabilityRepository
from backend.modules.orders.application.dto import (
    OrderCareObjectSnapshot,
    OrderData,
    OrderDTO,
    PricePreviewDTO,
    ServicePricingDTO,
)
from backend.modules.orders.application.interfaces import (
    OrderRepository,
    PricingRepository,
)
from backend.modules.orders.application.pricing import (
    CalculatePricePreviewCommand,
    CalculatePricePreviewUseCase,
)


@dataclass(frozen=True)
class OrderCommand:
    customer_id: UUID
    service_id: UUID
    start_at: datetime
    end_at: datetime
    care_object_ids: tuple[UUID, ...]
    address_id: UUID | None
    customer_comment: str | None
    report_photo_consent: bool | None
    option_values: dict[UUID, Any]


@dataclass(frozen=True)
class CreatePoolOrderCommand(OrderCommand):
    pass


@dataclass(frozen=True)
class CreateDirectOrderCommand(OrderCommand):
    performer_id: UUID


class CreatePoolOrderUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        pricing_repository: PricingRepository,
    ) -> None:
        self._order_repository = order_repository
        self._pricing_repository = pricing_repository

    async def execute(self, command: CreatePoolOrderCommand) -> OrderDTO:
        data, service, price, snapshots, deadline = await _prepare_order(
            command,
            self._order_repository,
            self._pricing_repository,
        )
        return await self._order_repository.create_pool(
            data=data,
            service=service,
            price=price,
            object_snapshots=snapshots,
            matching_deadline_minutes=deadline,
        )


class CreateDirectOrderUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        pricing_repository: PricingRepository,
        availability_repository: AvailabilityRepository,
    ) -> None:
        self._order_repository = order_repository
        self._pricing_repository = pricing_repository
        self._availability_repository = availability_repository

    async def execute(self, command: CreateDirectOrderCommand) -> OrderDTO:
        response_window = await self._pricing_repository.get_integer_setting(
            "direct_response_window_minutes",
        )
        if response_window is None:
            raise ValidationError("Direct response window is not configured")
        data, service, price, snapshots, deadline = await _prepare_order(
            command,
            self._order_repository,
            self._pricing_repository,
        )
        await self._ensure_direct_performer_suitable(command)
        return await self._order_repository.create_direct(
            data=data,
            service=service,
            price=price,
            object_snapshots=snapshots,
            matching_deadline_minutes=deadline,
            performer_id=command.performer_id,
            response_window_minutes=response_window,
        )

    async def _ensure_direct_performer_suitable(
        self,
        command: CreateDirectOrderCommand,
    ) -> None:
        city_id = await self._order_repository.get_customer_city_id(command.customer_id)
        if city_id is None:
            raise ValidationError("Customer is inactive or unknown")
        suitable = await self._availability_repository.find_suitable_performers(
            city_id=city_id,
            service_id=command.service_id,
            starts_at=command.start_at,
            ends_at=command.end_at,
            objects_count=len(command.care_object_ids),
            care_object_ids=command.care_object_ids,
            address_id=command.address_id,
            limit=100,
        )
        if all(item.performer_id != command.performer_id for item in suitable):
            raise ValidationError("Performer is not suitable for direct order")


async def _prepare_order(
    command: OrderCommand,
    order_repository: OrderRepository,
    pricing_repository: PricingRepository,
) -> tuple[
    OrderData,
    ServicePricingDTO,
    PricePreviewDTO,
    tuple[OrderCareObjectSnapshot, ...],
    int,
]:
    service = await pricing_repository.get_service_pricing(command.service_id)
    if service is None:
        raise NotFoundError("Service not found")
    if await order_repository.get_customer_city_id(command.customer_id) is None:
        raise ValidationError("Customer is inactive or unknown")
    if not command.care_object_ids:
        raise ValidationError("Order must include care objects")
    snapshots = await order_repository.list_care_object_snapshots(
        customer_id=command.customer_id,
        care_object_ids=command.care_object_ids,
    )
    if len(snapshots) != len(set(command.care_object_ids)):
        raise ValidationError("Care object is inactive or unknown")
    if len(snapshots) > service.max_objects_per_order:
        raise ValidationError("Order objects count exceeds service limit")
    if any(
        snapshot.object_type != service.category_object_type for snapshot in snapshots
    ):
        raise ValidationError("Care object category does not match service")
    if service.location_policy == "customer_address":
        if command.address_id is None:
            raise ValidationError("Customer address is required")
        if not await order_repository.customer_address_is_active(
            customer_id=command.customer_id,
            address_id=command.address_id,
        ):
            raise ValidationError("Customer address is inactive or unknown")
    elif service.location_policy == "performer_address":
        if command.address_id is not None:
            raise ValidationError("Boarding order must not use customer address")
    else:
        raise ValidationError("Service location policy is invalid")
    if service.photo_policy == "requires_customer_consent":
        if command.report_photo_consent is None:
            raise ValidationError("Report photo consent is required")
    elif command.report_photo_consent is not None:
        raise ValidationError("Report photo consent is not allowed for this service")
    if not await order_repository.service_options_exist(
        service_id=command.service_id,
        option_values=command.option_values,
    ):
        raise ValidationError("Service option is inactive or unknown")
    price = await CalculatePricePreviewUseCase(pricing_repository).execute(
        CalculatePricePreviewCommand(
            service_id=command.service_id,
            start_at=command.start_at,
            end_at=command.end_at,
            objects_count=len(snapshots),
        ),
    )
    matching_deadline_minutes = await pricing_repository.get_integer_setting(
        "matching_close_before_start_minutes",
    )
    if matching_deadline_minutes is None:
        raise ValidationError("Matching deadline setting is not configured")
    data = OrderData(
        customer_id=command.customer_id,
        service_id=command.service_id,
        start_at=command.start_at,
        end_at=command.end_at,
        care_object_ids=command.care_object_ids,
        address_id=command.address_id,
        customer_comment=command.customer_comment,
        report_photo_consent=command.report_photo_consent,
        option_values=command.option_values,
    )
    return data, service, price, snapshots, matching_deadline_minutes

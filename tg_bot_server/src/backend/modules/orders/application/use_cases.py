from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from backend.common.domain import NotFoundError, ValidationError
from backend.modules.orders.application.dto import (
    DraftOrderData,
    OrderCareObjectSnapshot,
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
class DraftOrderCommand:
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
class CreateDraftOrderCommand(DraftOrderCommand):
    pass


@dataclass(frozen=True)
class UpdateDraftOrderCommand(DraftOrderCommand):
    order_id: UUID


class CreateDraftOrderUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        pricing_repository: PricingRepository,
    ) -> None:
        self._order_repository = order_repository
        self._pricing_repository = pricing_repository

    async def execute(self, command: CreateDraftOrderCommand) -> OrderDTO:
        data, service, price, snapshots, deadline = await _prepare_draft(
            command,
            self._order_repository,
            self._pricing_repository,
        )
        return await self._order_repository.create_draft(
            data=data,
            service=service,
            price=price,
            object_snapshots=snapshots,
            matching_deadline_minutes=deadline,
        )


class UpdateDraftOrderUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        pricing_repository: PricingRepository,
    ) -> None:
        self._order_repository = order_repository
        self._pricing_repository = pricing_repository

    async def execute(self, command: UpdateDraftOrderCommand) -> OrderDTO:
        data, service, price, snapshots, deadline = await _prepare_draft(
            command,
            self._order_repository,
            self._pricing_repository,
        )
        order = await self._order_repository.replace_draft(
            order_id=command.order_id,
            data=data,
            service=service,
            price=price,
            object_snapshots=snapshots,
            matching_deadline_minutes=deadline,
        )
        if order is None:
            raise NotFoundError("Draft order not found")
        return order


class CancelDraftOrderUseCase:
    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository

    async def execute(self, order_id: UUID) -> OrderDTO:
        order = await self._repository.cancel_draft(order_id)
        if order is None:
            raise NotFoundError("Draft order not found")
        return order


class PublishPoolOrderUseCase:
    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository

    async def execute(self, order_id: UUID) -> OrderDTO:
        order = await self._repository.publish_pool(order_id)
        if order is None:
            raise NotFoundError("Draft order not found")
        return order


@dataclass(frozen=True)
class PublishDirectOrderCommand:
    order_id: UUID
    performer_id: UUID


class PublishDirectOrderUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        pricing_repository: PricingRepository,
    ) -> None:
        self._order_repository = order_repository
        self._pricing_repository = pricing_repository

    async def execute(self, command: PublishDirectOrderCommand) -> OrderDTO:
        response_window = await self._pricing_repository.get_integer_setting(
            "direct_response_window_minutes",
        )
        if response_window is None:
            raise ValidationError("Direct response window is not configured")
        order = await self._order_repository.publish_direct(
            order_id=command.order_id,
            performer_id=command.performer_id,
            response_window_minutes=response_window,
        )
        if order is None:
            raise NotFoundError("Draft order not found")
        return order


async def _prepare_draft(
    command: DraftOrderCommand,
    order_repository: OrderRepository,
    pricing_repository: PricingRepository,
) -> tuple[
    DraftOrderData,
    ServicePricingDTO,
    PricePreviewDTO,
    tuple[OrderCareObjectSnapshot, ...],
    int,
]:
    service = await pricing_repository.get_service_pricing(command.service_id)
    if service is None:
        raise NotFoundError("Service not found")
    if not command.care_object_ids:
        raise ValidationError("Order must include care objects")
    snapshots = await order_repository.list_care_object_snapshots(
        customer_id=command.customer_id,
        care_object_ids=command.care_object_ids,
    )
    if len(snapshots) != len(set(command.care_object_ids)):
        raise ValidationError("Care object is inactive or unknown")
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
    data = DraftOrderData(
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


__all__ = [
    "CancelDraftOrderUseCase",
    "CreateDraftOrderCommand",
    "CreateDraftOrderUseCase",
    "PublishDirectOrderCommand",
    "PublishDirectOrderUseCase",
    "PublishPoolOrderUseCase",
    "UpdateDraftOrderCommand",
    "UpdateDraftOrderUseCase",
]

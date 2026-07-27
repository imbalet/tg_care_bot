from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from backend.common.application import ObjectStorage, to_utc, utc_now
from backend.common.domain import NotFoundError, ValidationError
from backend.modules.availability.application import AvailabilityRepository
from backend.modules.files.application import (
    CreateFileLinkCommand,
    FileRepository,
    validate_image_content,
)
from backend.modules.orders.application.dto import (
    OrderCareObjectSnapshot,
    OrderData,
    OrderDTO,
    OrderReportDTO,
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
    location_source: str | None


@dataclass(frozen=True)
class CreatePoolOrderCommand(OrderCommand):
    pass


@dataclass(frozen=True)
class CreateDirectOrderCommand(OrderCommand):
    performer_id: UUID


@dataclass(frozen=True)
class StartOrderCommand:
    order_id: UUID
    performer_id: UUID


@dataclass(frozen=True)
class StartOrderByCustomerCommand:
    order_id: UUID
    customer_id: UUID


@dataclass(frozen=True)
class FinishOrderCommand:
    order_id: UUID
    performer_id: UUID


@dataclass(frozen=True)
class ConfirmReportCommand:
    order_id: UUID
    customer_id: UUID


@dataclass(frozen=True)
class SubmitOrderReportCommand:
    order_id: UUID
    performer_id: UUID
    completed_work: str
    comment: str | None
    problem_flag: bool
    problem_description: str | None
    file_ids: tuple[UUID, ...]


class ConfirmReportUseCase:
    def __init__(
        self, repository: OrderRepository, pricing_repository: PricingRepository
    ) -> None:
        self._repository = repository
        self._pricing_repository = pricing_repository

    async def execute(self, command: ConfirmReportCommand) -> OrderDTO:
        window = await self._pricing_repository.get_integer_setting(
            "report_confirmation_window_minutes",
        )
        if window is None:
            raise ValidationError("Report confirmation policy is not configured")
        return await self._repository.confirm_report(
            order_id=command.order_id,
            customer_id=command.customer_id,
            confirmation_window_minutes=window,
        )


@dataclass(frozen=True)
class CancelOrderCommand:
    order_id: UUID
    actor_type: str
    actor_id: UUID
    reason: str | None = None
    comment: str | None = None


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


class StartOrderByCustomerUseCase:
    def __init__(
        self,
        repository: OrderRepository,
        pricing_repository: PricingRepository,
    ) -> None:
        self._repository = repository
        self._pricing_repository = pricing_repository

    async def execute(self, command: StartOrderByCustomerCommand) -> OrderDTO:
        start_window = await self._pricing_repository.get_integer_setting(
            "start_button_before_minutes",
        )
        if start_window is None:
            raise ValidationError("Start button policy is not configured")
        return await self._repository.start_order_by_customer(
            order_id=command.order_id,
            customer_id=command.customer_id,
            start_button_before_minutes=start_window,
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
        await self._ensure_direct_performer_suitable(
            command=command,
            starts_at=data.start_at,
            ends_at=data.end_at,
        )
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
        *,
        command: CreateDirectOrderCommand,
        starts_at: datetime,
        ends_at: datetime,
    ) -> None:
        city_id = await self._order_repository.get_customer_city_id(command.customer_id)
        if city_id is None:
            raise ValidationError("Customer is inactive or unknown")
        suitable = await self._availability_repository.find_suitable_performers(
            city_id=city_id,
            service_id=command.service_id,
            starts_at=starts_at,
            ends_at=ends_at,
            objects_count=len(command.care_object_ids),
            care_object_ids=command.care_object_ids,
            address_id=command.address_id,
            limit=100,
        )
        if all(item.performer_id != command.performer_id for item in suitable):
            raise ValidationError("Performer is not suitable for direct order")


class StartOrderUseCase:
    def __init__(
        self, repository: OrderRepository, pricing_repository: PricingRepository
    ) -> None:
        self._repository = repository
        self._pricing_repository = pricing_repository

    async def execute(self, command: StartOrderCommand) -> OrderDTO:
        start_window = await self._pricing_repository.get_integer_setting(
            "start_button_before_minutes",
        )
        if start_window is None:
            raise ValidationError("Start button policy is not configured")
        return await self._repository.start_order(
            order_id=command.order_id,
            performer_id=command.performer_id,
            start_button_before_minutes=start_window,
        )


class FinishOrderUseCase:
    def __init__(
        self,
        repository: OrderRepository,
        pricing_repository: PricingRepository,
    ) -> None:
        self._repository = repository
        self._pricing_repository = pricing_repository

    async def execute(self, command: FinishOrderCommand) -> OrderDTO:
        grace_minutes = await self._pricing_repository.get_integer_setting(
            "report_deadline_minutes",
        )
        if grace_minutes is None:
            raise ValidationError("Report deadline is not configured")
        return await self._repository.finish_order(
            order_id=command.order_id,
            performer_id=command.performer_id,
            report_due_at=utc_now() + timedelta(minutes=grace_minutes),
        )


class SubmitOrderReportUseCase:
    def __init__(
        self,
        repository: OrderRepository,
        file_repository: FileRepository,
        storage: ObjectStorage,
        pricing_repository: PricingRepository | None = None,
    ) -> None:
        self._repository = repository
        self._file_repository = file_repository
        self._storage = storage
        self._pricing_repository = pricing_repository

    async def execute(self, command: SubmitOrderReportCommand) -> OrderReportDTO:
        if not command.completed_work.strip():
            raise ValidationError("Completed work is required")
        if command.problem_flag and not command.problem_description:
            raise ValidationError("Problem description is required")
        if not command.problem_flag and command.problem_description:
            raise ValidationError("Problem description is not allowed")
        files = []
        for file_id in command.file_ids:
            file = await self._file_repository.get(file_id)
            if file is None or file.status != "uploaded":
                raise ValidationError("Report file is unavailable")
            if file.storage_key is None:
                raise ValidationError("Report file content is unavailable")
            content = await self._storage.get(file.storage_key)
            validate_image_content(
                content=content,
                content_type=file.mime_type,
                max_bytes=10 * 1024 * 1024,
            )
            files.append(file)
        order = await self._repository.get_order(command.order_id)
        if order is None:
            raise NotFoundError("Order not found")
        if order.photo_policy == "required" and not files:
            raise ValidationError("Report photo is required")
        if (
            order.photo_policy == "requires_customer_consent"
            and files
            and order.report_photo_consent is not True
        ):
            raise ValidationError("Report photo consent is not granted")
        confirmation_minutes = 24 * 60
        if self._pricing_repository is not None:
            configured_minutes = await self._pricing_repository.get_integer_setting(
                "report_confirmation_window_minutes"
            )
            if configured_minutes is None:
                raise ValidationError("Report confirmation policy is not configured")
            confirmation_minutes = configured_minutes
        report = await self._repository.submit_report(
            order_id=command.order_id,
            performer_id=command.performer_id,
            completed_work=command.completed_work,
            comment=command.comment,
            problem_flag=command.problem_flag,
            problem_description=command.problem_description,
            confirmation_deadline_at=utc_now()
            + timedelta(minutes=confirmation_minutes),
        )
        for index, file in enumerate(files):
            await self._file_repository.add_link(
                CreateFileLinkCommand(
                    file_id=file.id,
                    entity_type="order_report",
                    entity_id=report.id,
                    purpose="report_photo",
                    sort_order=index,
                ),
            )
        return OrderReportDTO(
            id=report.id,
            order_id=report.order_id,
            performer_id=report.performer_id,
            completed_work=report.completed_work,
            comment=report.comment,
            problem_flag=report.problem_flag,
            problem_description=report.problem_description,
            submitted_at=report.submitted_at,
            file_ids=command.file_ids,
        )


class CancelOrderUseCase:
    def __init__(
        self,
        repository: OrderRepository,
        pricing_repository: PricingRepository,
    ) -> None:
        self._repository = repository
        self._pricing_repository = pricing_repository

    async def execute(self, command: CancelOrderCommand) -> OrderDTO:
        customer_minutes = await self._pricing_repository.get_integer_setting(
            "customer_cancel_before_start_minutes",
        )
        performer_minutes = await self._pricing_repository.get_integer_setting(
            "performer_cancel_before_start_minutes",
        )
        if customer_minutes is None or performer_minutes is None:
            raise ValidationError("Cancel policy is not configured")
        return await self._repository.cancel_order(
            order_id=command.order_id,
            actor_type=command.actor_type,
            actor_id=command.actor_id,
            customer_deadline_minutes=customer_minutes,
            performer_deadline_minutes=performer_minutes,
            reason=command.reason,
            comment=command.comment,
        )


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
    timezone = await order_repository.get_customer_timezone(command.customer_id)
    if timezone is None:
        raise ValidationError("Customer is inactive or unknown")
    start_at = to_utc(command.start_at, timezone)
    end_at = to_utc(command.end_at, timezone)
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
    if service.location_policy == "customer_or_performer_address":
        if command.location_source not in {"customer_address", "performer_address"}:
            raise ValidationError("Order location source is required")
        location_source = command.location_source
    elif service.location_policy in {"customer_address", "performer_address"}:
        location_source = service.location_policy
        if (
            command.location_source is not None
            and command.location_source != location_source
        ):
            raise ValidationError("Order location source is not allowed")
    else:
        raise ValidationError("Service location policy is invalid")

    if location_source == "customer_address":
        if command.address_id is None:
            raise ValidationError("Customer address is required")
        if not await order_repository.customer_address_is_active(
            customer_id=command.customer_id,
            address_id=command.address_id,
        ):
            raise ValidationError("Customer address is inactive or unknown")
    elif location_source == "performer_address":
        if command.address_id is not None:
            raise ValidationError(
                "Performer address order must not use customer address"
            )
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
            customer_id=command.customer_id,
            service_id=command.service_id,
            start_at=start_at,
            end_at=end_at,
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
        start_at=start_at,
        end_at=end_at,
        care_object_ids=command.care_object_ids,
        address_id=command.address_id,
        customer_comment=command.customer_comment,
        report_photo_consent=command.report_photo_consent,
        option_values=command.option_values,
        timezone=timezone,
        location_source=location_source,
    )
    return data, service, price, snapshots, matching_deadline_minutes

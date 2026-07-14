from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from backend.common.domain import ValidationError
from backend.modules.orders.application import (
    CreateDirectOrderCommand,
    CreateDirectOrderUseCase,
    CreatePoolOrderCommand,
    CreatePoolOrderUseCase,
    DraftOrderData,
    OrderCareObjectSnapshot,
    OrderDTO,
    PricePreviewDTO,
    ServicePricingDTO,
)


class FakeOrderRepository:
    def __init__(self) -> None:
        self.customer_id = uuid4()
        self.care_object_id = uuid4()
        self.address_id = uuid4()
        self.published_direct_window: int | None = None

    async def get_order(self, order_id: UUID) -> OrderDTO | None:
        return None

    async def create_draft(
        self,
        *,
        data: DraftOrderData,
        service: ServicePricingDTO,
        price: PricePreviewDTO,
        object_snapshots: tuple[OrderCareObjectSnapshot, ...],
        matching_deadline_minutes: int,
    ) -> OrderDTO:
        return _order_dto(
            service=service,
            price=price,
            data=data,
            status="draft",
            matching_mode=None,
            matching_deadline_minutes=matching_deadline_minutes,
        )

    async def create_pool(
        self,
        *,
        data: DraftOrderData,
        service: ServicePricingDTO,
        price: PricePreviewDTO,
        object_snapshots: tuple[OrderCareObjectSnapshot, ...],
        matching_deadline_minutes: int,
    ) -> OrderDTO:
        return _order_dto(
            service=service,
            price=price,
            data=data,
            status="searching",
            matching_mode="pool",
            matching_deadline_minutes=matching_deadline_minutes,
        )

    async def create_direct(
        self,
        *,
        data: DraftOrderData,
        service: ServicePricingDTO,
        price: PricePreviewDTO,
        object_snapshots: tuple[OrderCareObjectSnapshot, ...],
        matching_deadline_minutes: int,
        performer_id: UUID,
        response_window_minutes: int,
    ) -> OrderDTO:
        self.published_direct_window = response_window_minutes
        return _order_dto(
            service=service,
            price=price,
            data=data,
            status="searching",
            matching_mode="direct",
            matching_deadline_minutes=matching_deadline_minutes,
        )

    async def replace_draft(
        self,
        *,
        order_id: UUID,
        data: DraftOrderData,
        service: ServicePricingDTO,
        price: PricePreviewDTO,
        object_snapshots: tuple[OrderCareObjectSnapshot, ...],
        matching_deadline_minutes: int,
    ) -> OrderDTO | None:
        return None

    async def cancel_draft(self, order_id: UUID) -> OrderDTO | None:
        return None

    async def publish_pool(self, order_id: UUID) -> OrderDTO | None:
        return None

    async def publish_direct(
        self,
        *,
        order_id: UUID,
        performer_id: UUID,
        response_window_minutes: int,
    ) -> OrderDTO | None:
        self.published_direct_window = response_window_minutes
        return OrderDTO(
            id=order_id,
            customer_id=self.customer_id,
            service_id=uuid4(),
            service_code="service",
            service_name="Service",
            schedule_policy="working_hours",
            photo_policy="required",
            matching_mode="direct",
            status="searching",
            address_id=self.address_id,
            location_source="customer_address",
            start_at=datetime.now(UTC) + timedelta(hours=8),
            end_at=datetime.now(UTC) + timedelta(hours=9),
            objects_count=1,
            total_amount=Decimal("100.00"),
            performer_amount=Decimal("95.00"),
            platform_fee_amount=Decimal("5.00"),
            matching_deadline_at=datetime.now(UTC) + timedelta(hours=4),
        )

    async def list_care_object_snapshots(
        self,
        *,
        customer_id: UUID,
        care_object_ids: tuple[UUID, ...],
    ) -> tuple[OrderCareObjectSnapshot, ...]:
        if (
            customer_id != self.customer_id
            or self.care_object_id not in care_object_ids
        ):
            return ()
        return (
            OrderCareObjectSnapshot(
                care_object_id=self.care_object_id,
                object_type="child",
                display_name_at_order="Child",
                summary_at_order="school_age",
            ),
        )

    async def customer_address_is_active(
        self,
        *,
        customer_id: UUID,
        address_id: UUID,
    ) -> bool:
        return customer_id == self.customer_id and address_id == self.address_id

    async def service_options_exist(
        self,
        *,
        service_id: UUID,
        option_values: dict[UUID, Any],
    ) -> bool:
        return True


class FakePricingRepository:
    def __init__(self, service: ServicePricingDTO) -> None:
        self.service = service

    async def get_service_pricing(self, service_id: UUID) -> ServicePricingDTO | None:
        return self.service if self.service.service_id == service_id else None

    async def get_object_multiplier(
        self,
        *,
        category_id: UUID,
        objects_count: int,
    ) -> Decimal | None:
        return Decimal("1.00")

    async def get_decimal_setting(self, key: str) -> Decimal | None:
        return Decimal("5") if key == "platform_fee_percent" else None

    async def get_integer_setting(self, key: str) -> int | None:
        settings = {
            "minimum_order_lead_minutes": 360,
            "matching_close_before_start_minutes": 210,
            "direct_response_window_minutes": 180,
            "report_confirmation_window_minutes": 1440,
        }
        return settings.get(key)


def make_service(photo_policy: str = "requires_customer_consent") -> ServicePricingDTO:
    return ServicePricingDTO(
        service_id=uuid4(),
        category_id=uuid4(),
        service_code="nanny_care",
        service_name="Присмотр",
        price_type="hourly",
        base_price=Decimal("100.00"),
        location_policy="customer_address",
        schedule_policy="working_hours",
        photo_policy=photo_policy,
        duration_step_minutes=60,
        min_duration_minutes=None,
        max_duration_minutes=None,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_create_pool_requires_photo_consent_for_policy() -> None:
    order_repository = FakeOrderRepository()
    service = make_service()

    with pytest.raises(ValidationError):
        await CreatePoolOrderUseCase(
            order_repository,
            FakePricingRepository(service),
        ).execute(_order_command(order_repository, service, report_photo_consent=None))


@pytest.mark.asyncio
async def test_create_pool_rejects_inactive_care_object() -> None:
    order_repository = FakeOrderRepository()
    service = make_service(photo_policy="required")
    command = _order_command(
        order_repository,
        service,
        care_object_ids=(uuid4(),),
        report_photo_consent=None,
    )

    with pytest.raises(ValidationError):
        await CreatePoolOrderUseCase(
            order_repository,
            FakePricingRepository(service),
        ).execute(command)


@pytest.mark.asyncio
async def test_create_direct_uses_configured_response_window() -> None:
    order_repository = FakeOrderRepository()
    service = make_service(photo_policy="required")

    command = _direct_order_command(order_repository, service)

    order = await CreateDirectOrderUseCase(
        order_repository,
        FakePricingRepository(service),
    ).execute(command)

    assert order.status == "searching"
    assert order.matching_mode == "direct"
    assert order_repository.published_direct_window == 180


def _order_command(
    repository: FakeOrderRepository,
    service: ServicePricingDTO,
    *,
    care_object_ids: tuple[UUID, ...] | None = None,
    report_photo_consent: bool | None = True,
) -> CreatePoolOrderCommand:
    now = datetime.now(UTC)
    return CreatePoolOrderCommand(
        customer_id=repository.customer_id,
        service_id=service.service_id,
        start_at=now + timedelta(hours=8),
        end_at=now + timedelta(hours=9),
        care_object_ids=care_object_ids or (repository.care_object_id,),
        address_id=repository.address_id,
        customer_comment=None,
        report_photo_consent=report_photo_consent,
        option_values={},
    )


def _direct_order_command(
    repository: FakeOrderRepository,
    service: ServicePricingDTO,
) -> CreateDirectOrderCommand:
    pool_command = _order_command(repository, service, report_photo_consent=None)
    return CreateDirectOrderCommand(
        performer_id=uuid4(),
        customer_id=pool_command.customer_id,
        service_id=pool_command.service_id,
        start_at=pool_command.start_at,
        end_at=pool_command.end_at,
        care_object_ids=pool_command.care_object_ids,
        address_id=pool_command.address_id,
        customer_comment=pool_command.customer_comment,
        report_photo_consent=pool_command.report_photo_consent,
        option_values=pool_command.option_values,
    )


def _order_dto(
    *,
    service: ServicePricingDTO,
    price: PricePreviewDTO,
    data: DraftOrderData,
    status: str,
    matching_mode: str | None,
    matching_deadline_minutes: int,
) -> OrderDTO:
    return OrderDTO(
        id=uuid4(),
        customer_id=data.customer_id,
        service_id=service.service_id,
        service_code=service.service_code,
        service_name=service.service_name,
        schedule_policy=service.schedule_policy,
        photo_policy=service.photo_policy,
        matching_mode=matching_mode,
        status=status,
        address_id=data.address_id,
        location_source=service.location_policy,
        start_at=data.start_at,
        end_at=data.end_at,
        objects_count=len(data.care_object_ids),
        total_amount=price.total_amount,
        performer_amount=price.performer_amount,
        platform_fee_amount=price.platform_fee_amount,
        matching_deadline_at=data.start_at
        - timedelta(minutes=matching_deadline_minutes),
    )

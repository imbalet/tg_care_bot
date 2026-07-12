from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from backend.common.domain import ValidationError
from backend.modules.orders.application import (
    CalculatePricePreviewCommand,
    CalculatePricePreviewUseCase,
    ServicePricingDTO,
)


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class FakePricingRepository:
    def __init__(self, service: ServicePricingDTO) -> None:
        self.service = service
        self.multiplier = Decimal("1.40")
        self.settings: dict[str, int | Decimal | None] = {
            "minimum_order_lead_minutes": 360,
            "platform_fee_percent": Decimal("5"),
            "payment_provider_hold_limit_minutes": None,
            "report_confirmation_window_minutes": 1440,
        }

    async def get_service_pricing(self, service_id: UUID) -> ServicePricingDTO | None:
        return self.service if self.service.service_id == service_id else None

    async def get_object_multiplier(
        self,
        *,
        category_id: UUID,
        objects_count: int,
    ) -> Decimal | None:
        return self.multiplier if category_id == self.service.category_id else None

    async def get_decimal_setting(self, key: str) -> Decimal | None:
        value = self.settings.get(key)
        return Decimal(str(value)) if value is not None else None

    async def get_integer_setting(self, key: str) -> int | None:
        value = self.settings.get(key)
        return int(value) if value is not None else None


def make_service(price_type: str, base_price: str) -> ServicePricingDTO:
    return ServicePricingDTO(
        service_id=uuid4(),
        category_id=uuid4(),
        service_code="service",
        service_name="Service",
        price_type=price_type,
        base_price=Decimal(base_price),
        location_policy="customer_address",
        schedule_policy="working_hours",
        photo_policy="required",
        duration_step_minutes=60,
        min_duration_minutes=None,
        max_duration_minutes=None,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_hourly_price_uses_duration_step_multiplier_and_fee() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    service = make_service("hourly", "100.00")
    repository = FakePricingRepository(service)

    preview = await CalculatePricePreviewUseCase(
        repository,
        FixedClock(now),
    ).execute(
        CalculatePricePreviewCommand(
            service_id=service.service_id,
            start_at=now + timedelta(hours=8),
            end_at=now + timedelta(hours=9, minutes=10),
            objects_count=2,
        ),
    )

    assert preview.billable_minutes == 120
    assert preview.service_amount == Decimal("280.00")
    assert preview.platform_fee_amount == Decimal("14.00")
    assert preview.performer_amount == Decimal("266.00")
    assert preview.total_amount == Decimal("280.00")
    assert preview.hold_limit_checked is False


@pytest.mark.asyncio
async def test_fixed_price_ignores_duration_amount() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    service = make_service("fixed", "500.00")
    repository = FakePricingRepository(service)

    preview = await CalculatePricePreviewUseCase(
        repository,
        FixedClock(now),
    ).execute(
        CalculatePricePreviewCommand(
            service_id=service.service_id,
            start_at=now + timedelta(hours=8),
            end_at=now + timedelta(hours=10),
            objects_count=2,
        ),
    )

    assert preview.billable_minutes is None
    assert preview.service_amount == Decimal("700.00")


@pytest.mark.asyncio
async def test_started_24h_price_rounds_up_units() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    service = make_service("started_24h", "1000.00")
    repository = FakePricingRepository(service)

    preview = await CalculatePricePreviewUseCase(
        repository,
        FixedClock(now),
    ).execute(
        CalculatePricePreviewCommand(
            service_id=service.service_id,
            start_at=now + timedelta(hours=8),
            end_at=now + timedelta(hours=33),
            objects_count=2,
        ),
    )

    assert preview.started_24h_units == 2
    assert preview.service_amount == Decimal("2800.00")


@pytest.mark.asyncio
async def test_lead_time_is_enforced() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    service = make_service("hourly", "100.00")

    with pytest.raises(ValidationError):
        await CalculatePricePreviewUseCase(
            FakePricingRepository(service),
            FixedClock(now),
        ).execute(
            CalculatePricePreviewCommand(
                service_id=service.service_id,
                start_at=now + timedelta(hours=2),
                end_at=now + timedelta(hours=3),
                objects_count=1,
            ),
        )


@pytest.mark.asyncio
async def test_configured_hold_limit_is_enforced() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    service = make_service("started_24h", "1000.00")
    repository = FakePricingRepository(service)
    repository.settings["payment_provider_hold_limit_minutes"] = 24 * 60

    with pytest.raises(ValidationError):
        await CalculatePricePreviewUseCase(repository, FixedClock(now)).execute(
            CalculatePricePreviewCommand(
                service_id=service.service_id,
                start_at=now + timedelta(hours=8),
                end_at=now + timedelta(hours=20),
                objects_count=1,
            ),
        )

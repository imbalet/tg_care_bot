from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.common.domain import ValidationError
from backend.modules.orders.application.dto import ServicePricingDTO
from backend.modules.orders.application.pricing import (
    CalculatePricePreviewCommand,
    CalculatePricePreviewUseCase,
)
from tests.support.fakes import FakeClock


def _service(*, price_type: str = "hourly") -> ServicePricingDTO:
    return ServicePricingDTO(
        service_id=uuid4(),
        category_id=uuid4(),
        category_object_type="pet",
        max_objects_per_order=3,
        service_code="walk",
        service_name="Walk",
        price_type=price_type,
        base_price=Decimal("600.00"),
        location_policy="customer_address",
        schedule_policy="working_hours",
        photo_policy="not_allowed",
        duration_step_minutes=30,
        min_duration_minutes=30,
        max_duration_minutes=240,
        is_active=True,
    )


def _repository(service: ServicePricingDTO) -> AsyncMock:
    repository = AsyncMock()
    repository.get_service_pricing.return_value = service
    repository.get_object_multiplier.return_value = Decimal("1.50")
    repository.get_decimal_setting.return_value = Decimal("10")
    repository.get_integer_setting.side_effect = lambda key: {
        "minimum_order_lead_minutes": 30,
        "payment_provider_hold_limit_minutes": 24 * 60,
        "report_confirmation_window_minutes": 60,
    }.get(key)
    return repository


@pytest.mark.unit
async def test_hourly_price_rounds_duration_and_splits_platform_fee() -> None:
    now = datetime(2026, 1, 1, 10, tzinfo=UTC)
    service = _service()
    result = await CalculatePricePreviewUseCase(
        _repository(service),
        FakeClock(now),
    ).execute(
        CalculatePricePreviewCommand(
            customer_id=uuid4(),
            service_id=service.service_id,
            start_at=now + timedelta(hours=2),
            end_at=now + timedelta(hours=3, minutes=1),
            objects_count=1,
        ),
    )

    assert result.duration_minutes == 61
    assert result.billable_minutes == 90
    assert result.service_amount == Decimal("1350.00")
    assert result.platform_fee_amount == Decimal("135.00")
    assert result.performer_amount == Decimal("1350.00")
    assert result.total_amount == Decimal("1485.00")


@pytest.mark.unit
async def test_price_rejects_missing_objects_and_invalid_duration() -> None:
    service = _service()
    repository = _repository(service)
    use_case = CalculatePricePreviewUseCase(
        repository,
        FakeClock(datetime(2026, 1, 1, 10, tzinfo=UTC)),
    )

    with pytest.raises(ValidationError):
        await use_case.execute(
            CalculatePricePreviewCommand(
                customer_id=uuid4(),
                service_id=service.service_id,
                start_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
                end_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
                objects_count=0,
            ),
        )


@pytest.mark.unit
async def test_price_rejects_order_beyond_payment_hold_limit() -> None:
    service = _service()
    repository = _repository(service)
    repository.get_integer_setting.side_effect = lambda key: {
        "minimum_order_lead_minutes": 30,
        "payment_provider_hold_limit_minutes": 60,
        "report_confirmation_window_minutes": 120,
    }.get(key)

    with pytest.raises(ValidationError, match="hold limit"):
        await CalculatePricePreviewUseCase(
            repository,
            FakeClock(datetime(2026, 1, 1, 10, tzinfo=UTC)),
        ).execute(
            CalculatePricePreviewCommand(
                customer_id=uuid4(),
                service_id=service.service_id,
                start_at=datetime(2026, 1, 1, 11, tzinfo=UTC),
                end_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
                objects_count=1,
            ),
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("price_type", "end_delta", "expected_units"),
    [
        ("fixed", timedelta(hours=2), None),
        ("started_24h", timedelta(hours=25), 2),
    ],
)
async def test_price_supports_fixed_and_started_24h_services(
    price_type: str,
    end_delta: timedelta,
    expected_units: int | None,
) -> None:
    now = datetime(2026, 1, 1, 10, tzinfo=UTC)
    service = replace(
        _service(price_type=price_type),
        max_duration_minutes=None,
        duration_step_minutes=1,
    )
    repository = _repository(service)
    repository.get_integer_setting.side_effect = lambda key: {
        "minimum_order_lead_minutes": 30,
        "payment_provider_hold_limit_minutes": 72 * 60,
        "report_confirmation_window_minutes": 60,
    }.get(key)

    result = await CalculatePricePreviewUseCase(
        repository,
        FakeClock(now),
    ).execute(
        CalculatePricePreviewCommand(
            customer_id=uuid4(),
            service_id=service.service_id,
            start_at=now + timedelta(hours=2),
            end_at=now + timedelta(hours=2) + end_delta,
            objects_count=1,
        ),
    )

    assert result.started_24h_units == expected_units
    assert result.billable_minutes is None


@pytest.mark.unit
async def test_price_rejects_missing_multiplier_and_fee_settings() -> None:
    service = _service()
    repository = _repository(service)
    repository.get_object_multiplier.return_value = None

    with pytest.raises(ValidationError, match="multiplier"):
        await CalculatePricePreviewUseCase(
            repository,
            FakeClock(datetime(2026, 1, 1, 10, tzinfo=UTC)),
        ).execute(
            CalculatePricePreviewCommand(
                customer_id=uuid4(),
                service_id=service.service_id,
                start_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
                end_at=datetime(2026, 1, 1, 13, tzinfo=UTC),
                objects_count=1,
            ),
        )

    repository.get_object_multiplier.return_value = Decimal("1")
    repository.get_decimal_setting.return_value = None
    with pytest.raises(ValidationError, match="fee"):
        await CalculatePricePreviewUseCase(
            repository,
            FakeClock(datetime(2026, 1, 1, 10, tzinfo=UTC)),
        ).execute(
            CalculatePricePreviewCommand(
                customer_id=uuid4(),
                service_id=service.service_id,
                start_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
                end_at=datetime(2026, 1, 1, 13, tzinfo=UTC),
                objects_count=1,
            ),
        )

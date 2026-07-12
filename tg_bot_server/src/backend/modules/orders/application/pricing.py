from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from backend.common.application import Clock, SystemClock
from backend.common.domain import NotFoundError, ValidationError
from backend.modules.orders.application.dto import PricePreviewDTO, ServicePricingDTO
from backend.modules.orders.application.interfaces import PricingRepository

MONEY_QUANT = Decimal("0.01")


@dataclass(frozen=True)
class CalculatePricePreviewCommand:
    service_id: UUID
    start_at: datetime
    end_at: datetime
    objects_count: int


class CalculatePricePreviewUseCase:
    def __init__(
        self,
        repository: PricingRepository,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or SystemClock()

    async def execute(self, command: CalculatePricePreviewCommand) -> PricePreviewDTO:
        if command.objects_count < 1:
            raise ValidationError("Objects count must be positive")
        if command.start_at >= command.end_at:
            raise ValidationError("Order start must be before end")
        service = await self._repository.get_service_pricing(command.service_id)
        if service is None or not service.is_active:
            raise NotFoundError("Service not found")
        duration_minutes = _ceil_minutes(command.start_at, command.end_at)
        _validate_duration(service, duration_minutes)
        await self._validate_lead_time(command.start_at)
        hold_limit_checked = await self._validate_hold_limit(command.end_at)
        object_multiplier = await self._repository.get_object_multiplier(
            category_id=service.category_id,
            objects_count=command.objects_count,
        )
        if object_multiplier is None:
            raise ValidationError("Object multiplier is not configured")
        platform_fee_percent = await self._repository.get_decimal_setting(
            "platform_fee_percent",
        )
        if platform_fee_percent is None:
            raise ValidationError("Platform fee percent is not configured")
        billable_minutes: int | None = None
        started_24h_units: int | None = None
        if service.price_type == "hourly":
            billable_minutes = _ceil_to_step(
                duration_minutes,
                service.duration_step_minutes,
            )
            service_amount = _money(
                service.base_price
                * Decimal(billable_minutes)
                / Decimal(60)
                * object_multiplier,
            )
        elif service.price_type == "fixed":
            service_amount = _money(service.base_price * object_multiplier)
        elif service.price_type == "started_24h":
            started_24h_units = _ceil_div(duration_minutes, 24 * 60)
            service_amount = _money(
                service.base_price * Decimal(started_24h_units) * object_multiplier,
            )
        else:
            raise ValidationError("Service price type is invalid")
        total_amount = service_amount
        platform_fee_amount = _money(total_amount * platform_fee_percent / Decimal(100))
        performer_amount = _money(total_amount - platform_fee_amount)
        return PricePreviewDTO(
            service_id=service.service_id,
            service_code=service.service_code,
            service_name=service.service_name,
            price_type=service.price_type,
            duration_minutes=duration_minutes,
            billable_minutes=billable_minutes,
            started_24h_units=started_24h_units,
            objects_count=command.objects_count,
            object_multiplier=object_multiplier,
            base_price=service.base_price,
            service_amount=service_amount,
            platform_fee_percent=platform_fee_percent,
            platform_fee_amount=platform_fee_amount,
            performer_amount=performer_amount,
            total_amount=total_amount,
            hold_limit_checked=hold_limit_checked,
        )

    async def _validate_lead_time(self, start_at: datetime) -> None:
        lead_minutes = await self._repository.get_integer_setting(
            "minimum_order_lead_minutes",
        )
        if lead_minutes is None:
            raise ValidationError("Minimum order lead time is not configured")
        if start_at < self._clock.now() + timedelta(minutes=lead_minutes):
            raise ValidationError("Order start is too soon")

    async def _validate_hold_limit(self, end_at: datetime) -> bool:
        hold_limit = await self._repository.get_integer_setting(
            "payment_provider_hold_limit_minutes",
        )
        if hold_limit is None:
            return False
        confirmation_window = await self._repository.get_integer_setting(
            "report_confirmation_window_minutes",
        )
        if confirmation_window is None:
            raise ValidationError("Report confirmation window is not configured")
        latest_payout_release = end_at + timedelta(minutes=confirmation_window)
        if latest_payout_release > self._clock.now() + timedelta(minutes=hold_limit):
            raise ValidationError("Order interval exceeds payment provider hold limit")
        return True


def _validate_duration(service: ServicePricingDTO, duration_minutes: int) -> None:
    min_duration = service.min_duration_minutes
    max_duration = service.max_duration_minutes
    if min_duration is not None and duration_minutes < min_duration:
        raise ValidationError("Order duration is shorter than service minimum")
    if max_duration is not None and duration_minutes > max_duration:
        raise ValidationError("Order duration is longer than service maximum")


def _ceil_minutes(start_at: datetime, end_at: datetime) -> int:
    return _ceil_div(int((end_at - start_at).total_seconds()), 60)


def _ceil_to_step(value: int, step: int) -> int:
    if step < 1:
        raise ValidationError("Duration step is not configured")
    return _ceil_div(value, step) * step


def _ceil_div(value: int, divisor: int) -> int:
    return -(-value // divisor)


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


__all__ = ["CalculatePricePreviewCommand", "CalculatePricePreviewUseCase"]

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.catalog.infrastructure import (
    BusinessSettingModel,
    ObjectCountMultiplierModel,
    ServiceModel,
)
from backend.modules.orders.application import PricingRepository, ServicePricingDTO


class SqlAlchemyPricingRepository(PricingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_service_pricing(self, service_id: UUID) -> ServicePricingDTO | None:
        model = await self._session.get(ServiceModel, service_id)
        if model is None:
            return None
        return ServicePricingDTO(
            service_id=model.id,
            category_id=model.category_id,
            service_code=model.code,
            service_name=model.name,
            price_type=model.price_type,
            base_price=model.base_price,
            location_policy=model.location_policy,
            schedule_policy=model.schedule_policy,
            photo_policy=model.photo_policy,
            duration_step_minutes=model.duration_step_minutes or 0,
            min_duration_minutes=model.min_duration_minutes,
            max_duration_minutes=model.max_duration_minutes,
            is_active=model.is_active,
        )

    async def get_object_multiplier(
        self,
        *,
        category_id: UUID,
        objects_count: int,
    ) -> Decimal | None:
        result = await self._session.execute(
            select(ObjectCountMultiplierModel.multiplier).where(
                ObjectCountMultiplierModel.category_id == category_id,
                ObjectCountMultiplierModel.objects_count == objects_count,
                ObjectCountMultiplierModel.is_active.is_(True),
            ),
        )
        return result.scalar_one_or_none()

    async def get_decimal_setting(self, key: str) -> Decimal | None:
        value = await self._get_setting_value(key)
        if value is None:
            return None
        return Decimal(str(value))

    async def get_integer_setting(self, key: str) -> int | None:
        value = await self._get_setting_value(key)
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int | float | Decimal | str):
            return int(value)
        msg = f"Business setting {key} is not numeric"
        raise ValueError(msg)

    async def _get_setting_value(self, key: str) -> object:
        result = await self._session.execute(
            select(BusinessSettingModel.value).where(BusinessSettingModel.key == key),
        )
        return result.scalar_one_or_none()

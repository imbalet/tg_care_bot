from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import utc_now
from backend.common.domain import ValidationError
from backend.modules.addresses.infrastructure import AddressModel
from backend.modules.care_objects.infrastructure import CareObjectModel
from backend.modules.catalog.infrastructure import CityModel, ServiceOptionModel
from backend.modules.customers.infrastructure import CustomerModel
from backend.modules.orders.application import (
    OrderCareObjectSnapshot,
    OrderData,
    OrderDTO,
    OrderRepository,
    PricePreviewDTO,
    ServicePricingDTO,
)
from backend.modules.orders.infrastructure.persistence.models import (
    OrderCareObjectModel,
    OrderMatchModel,
    OrderModel,
    OrderOptionValueModel,
    OrderStatusHistoryModel,
)
from backend.modules.performers.infrastructure import (
    PerformerModel,
    PerformerServiceModel,
)


class SqlAlchemyOrderRepository(OrderRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_order(self, order_id: UUID) -> OrderDTO | None:
        model = await self._session.get(OrderModel, order_id)
        return await self._order_to_dto(model) if model is not None else None

    async def create_pool(
        self,
        *,
        data: OrderData,
        service: ServicePricingDTO,
        price: PricePreviewDTO,
        object_snapshots: tuple[OrderCareObjectSnapshot, ...],
        matching_deadline_minutes: int,
    ) -> OrderDTO:
        model = _build_order_model(
            data=data,
            service=service,
            price=price,
            matching_deadline_minutes=matching_deadline_minutes,
        )
        model.matching_mode = "pool"
        self._session.add(model)
        await self._session.flush()
        self._replace_children(model.id, object_snapshots, data.option_values)
        self._add_status_history(model.id, None, "searching")
        await self._session.flush()
        return _order_to_dto(model, data.timezone)

    async def create_direct(
        self,
        *,
        data: OrderData,
        service: ServicePricingDTO,
        price: PricePreviewDTO,
        object_snapshots: tuple[OrderCareObjectSnapshot, ...],
        matching_deadline_minutes: int,
        performer_id: UUID,
        response_window_minutes: int,
    ) -> OrderDTO:
        model = _build_order_model(
            data=data,
            service=service,
            price=price,
            matching_deadline_minutes=matching_deadline_minutes,
        )
        model.matching_mode = "direct"
        self._session.add(model)
        await self._session.flush()
        if not await self._performer_can_receive_direct(model, performer_id):
            raise ValidationError("Performer is not suitable for direct order")
        now = utc_now()
        self._session.add(
            OrderMatchModel(
                order_id=model.id,
                performer_id=performer_id,
                source="direct",
                status="pending",
                starts_at=model.start_at,
                ends_at=model.end_at,
                response_expires_at=now + timedelta(minutes=response_window_minutes),
            ),
        )
        self._replace_children(model.id, object_snapshots, data.option_values)
        self._add_status_history(model.id, None, "searching")
        await self._session.flush()
        return _order_to_dto(model, data.timezone)

    async def _performer_can_receive_direct(
        self,
        order: OrderModel,
        performer_id: UUID,
    ) -> bool:
        result = await self._session.execute(
            select(PerformerModel, PerformerServiceModel)
            .join(
                PerformerServiceModel,
                PerformerServiceModel.performer_id == PerformerModel.id,
            )
            .where(
                PerformerModel.id == performer_id,
                PerformerModel.status == "active",
                PerformerModel.is_accepting_orders.is_(True),
                PerformerServiceModel.service_id == order.service_id,
                PerformerServiceModel.is_approved.is_(True),
                PerformerServiceModel.is_enabled.is_(True),
                PerformerServiceModel.performer_max_objects >= order.objects_count,
            ),
        )
        return result.first() is not None

    async def list_care_object_snapshots(
        self,
        *,
        customer_id: UUID,
        care_object_ids: tuple[UUID, ...],
    ) -> tuple[OrderCareObjectSnapshot, ...]:
        result = await self._session.execute(
            select(CareObjectModel).where(
                CareObjectModel.customer_id == customer_id,
                CareObjectModel.id.in_(care_object_ids),
                CareObjectModel.deleted_at.is_(None),
            ),
        )
        objects_by_id = {model.id: model for model in result.scalars()}
        return tuple(
            _care_object_snapshot(objects_by_id[care_object_id])
            for care_object_id in care_object_ids
            if care_object_id in objects_by_id
        )

    async def customer_address_is_active(
        self,
        *,
        customer_id: UUID,
        address_id: UUID,
    ) -> bool:
        result = await self._session.execute(
            select(AddressModel.id).where(
                AddressModel.id == address_id,
                AddressModel.customer_id == customer_id,
                AddressModel.deleted_at.is_(None),
            ),
        )
        return result.scalar_one_or_none() is not None

    async def get_customer_city_id(self, customer_id: UUID) -> UUID | None:
        result = await self._session.execute(
            select(CustomerModel.city_id).where(
                CustomerModel.id == customer_id,
                CustomerModel.status == "active",
                CustomerModel.deleted_at.is_(None),
            ),
        )
        return result.scalar_one_or_none()

    async def get_customer_timezone(self, customer_id: UUID) -> str | None:
        result = await self._session.execute(
            select(CityModel.timezone)
            .join(CustomerModel, CustomerModel.city_id == CityModel.id)
            .where(
                CustomerModel.id == customer_id,
                CustomerModel.status == "active",
                CustomerModel.deleted_at.is_(None),
                CityModel.is_active.is_(True),
            ),
        )
        return result.scalar_one_or_none()

    async def _order_to_dto(self, model: OrderModel) -> OrderDTO:
        if model.customer_id is None:
            raise ValidationError("Order customer is required")
        timezone = await self.get_customer_timezone(model.customer_id)
        if timezone is None:
            raise ValidationError("Order customer city is invalid")
        return _order_to_dto(model, timezone)

    async def service_options_exist(
        self,
        *,
        service_id: UUID,
        option_values: dict[UUID, Any],
    ) -> bool:
        result = await self._session.execute(
            select(ServiceOptionModel).where(
                ServiceOptionModel.service_id == service_id,
                ServiceOptionModel.is_active.is_(True),
            ),
        )
        options = tuple(result.scalars())
        options_by_id = {option.id: option for option in options}
        provided_ids = set(option_values)
        required_ids = {option.id for option in options if option.is_required}
        if not provided_ids.issubset(options_by_id):
            return False
        if not required_ids.issubset(provided_ids):
            return False
        return all(
            _option_value_matches(options_by_id[option_id].value_type, value)
            for option_id, value in option_values.items()
        )

    def _replace_children(
        self,
        order_id: UUID,
        snapshots: tuple[OrderCareObjectSnapshot, ...],
        option_values: dict[UUID, Any],
    ) -> None:
        for snapshot in snapshots:
            self._session.add(
                OrderCareObjectModel(
                    order_id=order_id,
                    care_object_id=snapshot.care_object_id,
                    object_type=snapshot.object_type,
                    display_name_at_order=snapshot.display_name_at_order,
                    summary_at_order=snapshot.summary_at_order,
                ),
            )
        for option_id, value in option_values.items():
            self._session.add(
                OrderOptionValueModel(
                    order_id=order_id,
                    service_option_id=option_id,
                    value=value,
                ),
            )

    def _add_status_history(
        self,
        order_id: UUID,
        from_status: str | None,
        to_status: str,
    ) -> None:
        self._session.add(
            OrderStatusHistoryModel(
                order_id=order_id,
                from_status=from_status,
                to_status=to_status,
                actor_type="customer",
                actor_id=None,
                reason=None,
            ),
        )


def _build_order_model(
    *,
    data: OrderData,
    service: ServicePricingDTO,
    price: PricePreviewDTO,
    matching_deadline_minutes: int,
) -> OrderModel:
    model = OrderModel()
    _apply_order_data(
        model=model,
        data=data,
        service=service,
        price=price,
        matching_deadline_minutes=matching_deadline_minutes,
    )
    return model


def _apply_order_data(
    *,
    model: OrderModel,
    data: OrderData,
    service: ServicePricingDTO,
    price: PricePreviewDTO,
    matching_deadline_minutes: int,
) -> None:
    model.customer_id = data.customer_id
    model.service_id = service.service_id
    model.service_code = service.service_code
    model.service_name = service.service_name
    model.schedule_policy = service.schedule_policy
    model.photo_policy = service.photo_policy
    model.matching_mode = None
    model.status = "searching"
    model.address_id = data.address_id
    model.location_source = service.location_policy
    model.start_at = data.start_at
    model.end_at = data.end_at
    model.objects_count = len(data.care_object_ids)
    model.customer_comment = data.customer_comment
    model.report_photo_consent = data.report_photo_consent
    model.base_price = price.base_price
    model.price_type = price.price_type
    model.object_multiplier = price.object_multiplier
    model.service_amount = price.service_amount
    model.platform_fee_percent_at_order = price.platform_fee_percent
    model.platform_fee_amount = price.platform_fee_amount
    model.performer_amount = price.performer_amount
    model.total_amount = price.total_amount
    model.matching_deadline_at = data.start_at - timedelta(
        minutes=matching_deadline_minutes,
    )
    model.requires_admin_attention = False


def _care_object_snapshot(model: CareObjectModel) -> OrderCareObjectSnapshot:
    return OrderCareObjectSnapshot(
        care_object_id=model.id,
        object_type=model.object_type,
        display_name_at_order=model.display_name,
        summary_at_order=_care_object_summary(model),
    )


def _care_object_summary(model: CareObjectModel) -> str | None:
    if model.object_type == "pet":
        values = [model.species, model.breed, model.pet_size]
    elif model.object_type == "ward":
        values = [model.age_group, f"mobility={model.mobility_assistance_required}"]
    else:
        values = [model.age_group]
    return ", ".join(value for value in values if value)


def _option_value_matches(value_type: str, value: Any) -> bool:
    if value_type == "boolean":
        return isinstance(value, bool)
    if value_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type == "decimal":
        if isinstance(value, bool) or not isinstance(value, int | float | str):
            return False
        try:
            Decimal(str(value))
        except InvalidOperation:
            return False
        return True
    if value_type == "string":
        return isinstance(value, str)
    return value_type == "json"


def _order_to_dto(model: OrderModel, timezone: str) -> OrderDTO:
    if model.customer_id is None:
        raise ValidationError("Order customer is required")
    return OrderDTO(
        id=model.id,
        customer_id=model.customer_id,
        service_id=model.service_id,
        service_code=model.service_code,
        service_name=model.service_name,
        schedule_policy=model.schedule_policy,
        photo_policy=model.photo_policy,
        matching_mode=model.matching_mode,
        status=model.status,
        address_id=model.address_id,
        location_source=model.location_source,
        start_at=model.start_at,
        end_at=model.end_at,
        objects_count=model.objects_count,
        total_amount=model.total_amount,
        performer_amount=model.performer_amount,
        platform_fee_amount=model.platform_fee_amount,
        matching_deadline_at=model.matching_deadline_at,
        timezone=timezone,
    )

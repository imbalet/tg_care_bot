from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import utc_now
from backend.common.domain import ValidationError
from backend.modules.addresses.infrastructure import AddressModel
from backend.modules.care_objects.infrastructure import CareObjectModel
from backend.modules.catalog.infrastructure import ServiceOptionModel
from backend.modules.orders.application import (
    DraftOrderData,
    OrderCareObjectSnapshot,
    OrderDTO,
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


class SqlAlchemyOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_order(self, order_id: UUID) -> OrderDTO | None:
        model = await self._session.get(OrderModel, order_id)
        return _order_to_dto(model) if model is not None else None

    async def create_draft(
        self,
        *,
        data: DraftOrderData,
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
        self._session.add(model)
        await self._session.flush()
        self._replace_children(model.id, object_snapshots, data.option_values)
        self._add_status_history(model.id, None, "draft")
        await self._session.flush()
        return _order_to_dto(model)

    async def create_pool(
        self,
        *,
        data: DraftOrderData,
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
        model.status = "searching"
        model.matching_mode = "pool"
        self._session.add(model)
        await self._session.flush()
        self._replace_children(model.id, object_snapshots, data.option_values)
        self._add_status_history(model.id, None, "searching")
        await self._session.flush()
        return _order_to_dto(model)

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
        model = _build_order_model(
            data=data,
            service=service,
            price=price,
            matching_deadline_minutes=matching_deadline_minutes,
        )
        model.status = "searching"
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
        return _order_to_dto(model)

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
        model = await self._session.get(OrderModel, order_id)
        if model is None or model.status != "draft":
            return None
        _apply_draft(
            model=model,
            data=data,
            service=service,
            price=price,
            matching_deadline_minutes=matching_deadline_minutes,
        )
        await self._delete_children(order_id)
        self._replace_children(order_id, object_snapshots, data.option_values)
        await self._session.flush()
        return _order_to_dto(model)

    async def cancel_draft(self, order_id: UUID) -> OrderDTO | None:
        model = await self._session.get(OrderModel, order_id)
        if model is None or model.status != "draft":
            return None
        model.status = "cancelled"
        model.cancelled_by = "customer"
        model.cancellation_reason = "customer_changed_plans"
        model.cancelled_at = utc_now()
        self._add_status_history(order_id, "draft", "cancelled")
        await self._session.flush()
        return _order_to_dto(model)

    async def publish_pool(self, order_id: UUID) -> OrderDTO | None:
        model = await self._session.get(OrderModel, order_id)
        if model is None or model.status != "draft":
            return None
        model.status = "searching"
        model.matching_mode = "pool"
        self._add_status_history(order_id, "draft", "searching")
        await self._session.flush()
        return _order_to_dto(model)

    async def publish_direct(
        self,
        *,
        order_id: UUID,
        performer_id: UUID,
        response_window_minutes: int,
    ) -> OrderDTO | None:
        model = await self._session.get(OrderModel, order_id)
        if model is None or model.status != "draft":
            return None
        if not await self._performer_can_receive_direct(model, performer_id):
            raise ValidationError("Performer is not suitable for direct order")
        now = utc_now()
        model.status = "searching"
        model.matching_mode = "direct"
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
        self._add_status_history(order_id, "draft", "searching")
        await self._session.flush()
        return _order_to_dto(model)

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

    async def service_options_exist(
        self,
        *,
        service_id: UUID,
        option_values: dict[UUID, Any],
    ) -> bool:
        if not option_values:
            return True
        result = await self._session.execute(
            select(ServiceOptionModel.id).where(
                ServiceOptionModel.service_id == service_id,
                ServiceOptionModel.id.in_(tuple(option_values)),
                ServiceOptionModel.is_active.is_(True),
            ),
        )
        return set(result.scalars()) == set(option_values)

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

    async def _delete_children(self, order_id: UUID) -> None:
        await self._session.execute(
            delete(OrderOptionValueModel).where(
                OrderOptionValueModel.order_id == order_id,
            ),
        )
        await self._session.execute(
            delete(OrderCareObjectModel).where(
                OrderCareObjectModel.order_id == order_id,
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
    data: DraftOrderData,
    service: ServicePricingDTO,
    price: PricePreviewDTO,
    matching_deadline_minutes: int,
) -> OrderModel:
    model = OrderModel()
    _apply_draft(
        model=model,
        data=data,
        service=service,
        price=price,
        matching_deadline_minutes=matching_deadline_minutes,
    )
    return model


def _apply_draft(
    *,
    model: OrderModel,
    data: DraftOrderData,
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
    model.status = "draft"
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


def _order_to_dto(model: OrderModel) -> OrderDTO:
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
    )


__all__ = ["SqlAlchemyOrderRepository"]

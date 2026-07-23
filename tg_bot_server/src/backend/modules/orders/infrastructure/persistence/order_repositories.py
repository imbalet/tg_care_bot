from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import utc_now
from backend.common.domain import ConflictError, NotFoundError, ValidationError
from backend.modules.addresses.infrastructure import AddressModel
from backend.modules.care_objects.infrastructure import CareObjectModel
from backend.modules.catalog.infrastructure import CityModel, ServiceOptionModel
from backend.modules.customers.infrastructure import CustomerModel
from backend.modules.notifications.infrastructure import NotificationModel
from backend.modules.orders.application import (
    CustomerPerformerProfileDTO,
    OrderCareObjectSnapshot,
    OrderData,
    OrderDTO,
    OrderReportDTO,
    OrderRepository,
    PricePreviewDTO,
    ServicePricingDTO,
)
from backend.modules.orders.infrastructure.persistence.models import (
    OrderCareObjectModel,
    OrderMatchModel,
    OrderModel,
    OrderOptionValueModel,
    OrderReportModel,
    OrderStatusHistoryModel,
)
from backend.modules.payments.infrastructure import PaymentModel, RefundModel
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

    async def get_customer_performer_profile(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> CustomerPerformerProfileDTO:
        result = await self._session.execute(
            select(PerformerModel)
            .join(OrderModel, OrderModel.selected_performer_id == PerformerModel.id)
            .where(
                OrderModel.id == order_id,
                OrderModel.customer_id == customer_id,
                OrderModel.status.in_(
                    (
                        "confirmed",
                        "in_progress",
                        "waiting_report",
                        "report_submitted",
                        "completed",
                    )
                ),
            )
        )
        performer = result.scalar_one_or_none()
        if performer is None:
            raise NotFoundError("Performer profile is not available")
        return CustomerPerformerProfileDTO(
            performer_id=performer.id,
            full_name=performer.full_name,
            about_text=performer.about_text,
            contact_method=performer.contact_method,
            telegram_username=performer.telegram_username,
        )

    async def start_order(self, *, order_id: UUID, performer_id: UUID) -> OrderDTO:
        order = await self._lock_order(order_id)
        if order.selected_performer_id != performer_id:
            raise NotFoundError("Order not found")
        if order.status != "confirmed":
            raise self._stale(order, "Order is not ready to start")
        now = utc_now()
        order.status = "in_progress"
        order.actual_started_at = now
        self._add_status_history(
            order.id,
            "confirmed",
            "in_progress",
            actor_type="performer",
            actor_id=performer_id,
            reason="performer_started",
        )
        self._add_notification(
            recipient_type="customer",
            customer_id=order.customer_id,
            notification_type="order_started",
            entity_id=order.id,
            deduplication_key=f"order-started:customer:{order.id}",
        )
        await self._session.flush()
        return await self._order_to_dto(order)

    async def start_order_by_customer(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> OrderDTO:
        order = await self._lock_order(order_id)
        if order.customer_id != customer_id:
            raise NotFoundError("Order not found")
        if order.status != "confirmed":
            raise self._stale(order, "Order is not ready to start")
        now = utc_now()
        order.status = "in_progress"
        order.actual_started_at = now
        self._add_status_history(
            order.id,
            "confirmed",
            "in_progress",
            actor_type="customer",
            actor_id=customer_id,
            reason="customer_started",
        )
        await self._session.flush()
        return await self._order_to_dto(order)

    async def finish_order(
        self,
        *,
        order_id: UUID,
        performer_id: UUID,
        report_due_at: datetime,
    ) -> OrderDTO:
        order = await self._lock_order(order_id)
        if order.selected_performer_id != performer_id:
            raise NotFoundError("Order not found")
        if order.status != "in_progress":
            raise self._stale(order, "Order is not in progress")
        now = utc_now()
        order.status = "waiting_report"
        order.actual_finished_at = now
        order.report_due_at = report_due_at
        self._add_status_history(
            order.id,
            "in_progress",
            "waiting_report",
            actor_type="performer",
            actor_id=performer_id,
            reason="performer_finished",
        )
        self._add_notification(
            recipient_type="customer",
            customer_id=order.customer_id,
            notification_type="order_finished",
            entity_id=order.id,
            deduplication_key=f"order-finished:{order.id}",
        )
        await self._session.flush()
        return await self._order_to_dto(order)

    async def submit_report(
        self,
        *,
        order_id: UUID,
        performer_id: UUID,
        completed_work: str,
        comment: str | None,
        problem_flag: bool,
        problem_description: str | None,
    ) -> OrderReportDTO:
        order = await self._lock_order(order_id)
        if order.selected_performer_id != performer_id:
            raise NotFoundError("Order not found")
        if order.status != "waiting_report":
            raise self._stale(order, "Order is not waiting for report")
        if (
            order.photo_policy == "requires_customer_consent"
            and order.report_photo_consent is not True
        ):
            raise ValidationError("Report photo consent is not granted")
        report = OrderReportModel(
            order_id=order.id,
            performer_id=performer_id,
            completed_work=completed_work,
            comment=comment,
            problem_flag=problem_flag,
            problem_description=problem_description,
        )
        self._session.add(report)
        now = utc_now()
        order.status = "report_submitted"
        order.actual_finished_at = order.actual_finished_at or now
        self._add_status_history(
            order.id,
            "waiting_report",
            "report_submitted",
            actor_type="performer",
            actor_id=performer_id,
            reason="report_submitted",
        )
        self._add_notification(
            recipient_type="customer",
            customer_id=order.customer_id,
            notification_type="report_submitted",
            entity_id=order.id,
            deduplication_key=f"report-submitted:{order.id}",
        )
        await self._session.flush()
        return OrderReportDTO(
            id=report.id,
            order_id=report.order_id,
            performer_id=report.performer_id,
            completed_work=report.completed_work,
            comment=report.comment,
            problem_flag=report.problem_flag,
            problem_description=report.problem_description,
            submitted_at=report.submitted_at,
            file_ids=(),
        )

    async def confirm_report(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
        confirmation_window_minutes: int,
    ) -> OrderDTO:
        order = await self._lock_order(order_id)
        if order.customer_id != customer_id:
            raise NotFoundError("Order not found")
        if order.status != "report_submitted":
            raise self._stale(order, "Order report is not awaiting confirmation")
        report = await self._session.scalar(
            select(OrderReportModel)
            .where(OrderReportModel.order_id == order.id)
            .order_by(OrderReportModel.created_at.desc())
            .limit(1),
        )
        if report is None:
            raise ValidationError("Order report is missing")
        if utc_now() > report.created_at + timedelta(
            minutes=confirmation_window_minutes,
        ):
            raise ConflictError("Report confirmation window has expired")
        order.status = "completed"
        self._add_status_history(
            order.id,
            "report_submitted",
            "completed",
            actor_type="customer",
            actor_id=customer_id,
            reason="customer_confirmed_report",
        )
        await self._session.flush()
        return await self._order_to_dto(order)

    async def cancel_order(
        self,
        *,
        order_id: UUID,
        actor_type: str,
        actor_id: UUID,
        customer_deadline_minutes: int,
        performer_deadline_minutes: int,
        reason: str | None = None,
        comment: str | None = None,
    ) -> OrderDTO:
        order = await self._lock_order(order_id)
        now = utc_now()
        if actor_type == "customer":
            if order.customer_id != actor_id:
                raise NotFoundError("Order not found")
            if order.status not in {"searching", "waiting_payment", "confirmed"}:
                raise self._stale(order, "Order cannot be cancelled")
            if now > order.start_at - timedelta(minutes=customer_deadline_minutes):
                raise ConflictError("Customer cancellation deadline has passed")
        elif actor_type == "performer":
            if order.selected_performer_id != actor_id:
                raise NotFoundError("Order not found")
            if order.status != "confirmed":
                raise self._stale(order, "Order cannot be cancelled")
            if now > order.start_at - timedelta(minutes=performer_deadline_minutes):
                raise ConflictError("Performer cancellation deadline has passed")
        elif actor_type != "admin":
            raise ValidationError("Invalid cancellation actor")
        if order.status in {"completed", "cancelled", "expired"}:
            raise self._stale(order, "Order cannot be cancelled")
        previous_status = order.status
        order.status = "cancelled"
        order.cancelled_by = actor_type
        order.cancellation_reason = reason or (
            "admin_decision" if actor_type == "admin" else f"{actor_type}_cancelled"
        )
        order.cancellation_comment = comment
        order.cancelled_at = now
        if order.active_payment_id is not None:
            payment = await self._session.get(PaymentModel, order.active_payment_id)
            if payment is not None and payment.status in {"created", "pending"}:
                payment.status = "cancelled"
            if payment is not None and payment.status == "succeeded":
                await self._create_customer_refund(order=order, payment=payment)
        matches = await self._session.execute(
            select(OrderMatchModel).where(
                OrderMatchModel.order_id == order.id,
                OrderMatchModel.status.in_({"pending", "active"}),
            ),
        )
        for match in matches.scalars():
            match.status = "cancelled"
        self._add_status_history(
            order.id,
            previous_status,
            "cancelled",
            actor_type=actor_type,
            actor_id=actor_id,
            reason=order.cancellation_reason,
        )
        await self._session.flush()
        return await self._order_to_dto(order)

    async def _create_customer_refund(
        self,
        *,
        order: OrderModel,
        payment: PaymentModel,
    ) -> None:
        remaining_minutes = int(
            max(0, (order.start_at - utc_now()).total_seconds()) // 60,
        )
        if remaining_minutes < 6 * 60:
            return
        amount = payment.amount
        refund_type = "full"
        if remaining_minutes <= 12 * 60:
            percent = order.partial_refund_percent_at_payment
            if percent is None:
                raise ValidationError("Partial refund policy is not available")
            amount = (amount * percent / Decimal("100")).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            refund_type = "partial"
        if amount <= 0:
            return
        idempotency_key = f"customer-cancellation:{order.id}:{payment.id}"
        existing = await self._session.scalar(
            select(RefundModel).where(
                RefundModel.idempotency_key == idempotency_key,
            ),
        )
        if existing is not None:
            return
        self._session.add(
            RefundModel(
                order_id=order.id,
                payment_id=payment.id,
                refund_type=refund_type,
                amount=amount,
                status="pending",
                reason="customer_cancellation",
                created_by_admin_id=None,
                idempotency_key=idempotency_key,
            ),
        )

    async def _lock_order(self, order_id: UUID) -> OrderModel:
        result = await self._session.execute(
            select(OrderModel).where(OrderModel.id == order_id).with_for_update(),
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise NotFoundError("Order not found")
        return order

    async def _lock_performer(self, performer_id: UUID) -> PerformerModel:
        result = await self._session.execute(
            select(PerformerModel)
            .where(PerformerModel.id == performer_id)
            .with_for_update(),
        )
        performer = result.scalar_one_or_none()
        if performer is None:
            raise NotFoundError("Performer not found")
        return performer

    async def _lock_overlapping_resources(
        self,
        *,
        performer_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
    ) -> None:
        await self._session.execute(
            select(OrderMatchModel)
            .where(
                OrderMatchModel.performer_id == performer_id,
                OrderMatchModel.status.in_(("active", "selected")),
                OrderMatchModel.starts_at < ends_at,
                OrderMatchModel.ends_at > starts_at,
            )
            .with_for_update(),
        )
        await self._session.execute(
            select(OrderModel)
            .where(
                OrderModel.selected_performer_id == performer_id,
                OrderModel.status == "confirmed",
                OrderModel.start_at < ends_at,
                OrderModel.end_at > starts_at,
            )
            .with_for_update(),
        )

    def _stale(self, order: OrderModel, message: str) -> ConflictError:
        return ConflictError(
            message,
            details={
                "current_order": {
                    "id": str(order.id),
                    "status": order.status,
                    "start_at": order.start_at.isoformat(),
                    "end_at": order.end_at.isoformat(),
                },
            },
        )

    def _add_notification(
        self,
        *,
        recipient_type: str,
        customer_id: UUID | None,
        notification_type: str,
        entity_id: UUID,
        deduplication_key: str,
    ) -> None:
        if customer_id is None:
            return
        now = utc_now()
        self._session.add(
            NotificationModel(
                recipient_type=recipient_type,
                customer_id=customer_id,
                performer_id=None,
                admin_id=None,
                channel="telegram",
                type=notification_type,
                entity_type="order",
                entity_id=entity_id,
                payload={"order_id": str(entity_id)},
                deduplication_key=deduplication_key,
                status="pending",
                attempts=0,
                scheduled_at=now,
                delete_after=now + timedelta(days=30),
            ),
        )

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
        await self._lock_performer(performer_id)
        await self._lock_overlapping_resources(
            performer_id=performer_id,
            starts_at=model.start_at,
            ends_at=model.end_at,
        )
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
            select(CareObjectModel)
            .where(
                CareObjectModel.customer_id == customer_id,
                CareObjectModel.id.in_(care_object_ids),
                CareObjectModel.deleted_at.is_(None),
            )
            .with_for_update(),
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
        *,
        actor_type: str = "customer",
        actor_id: UUID | None = None,
        reason: str | None = None,
    ) -> None:
        self._session.add(
            OrderStatusHistoryModel(
                order_id=order_id,
                from_status=from_status,
                to_status=to_status,
                actor_type=actor_type,
                actor_id=actor_id,
                reason=reason,
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

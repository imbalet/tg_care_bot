from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import utc_now
from backend.common.domain import ConflictError, NotFoundError, ValidationError
from backend.modules.availability.infrastructure import SqlAlchemyAvailabilityRepository
from backend.modules.catalog.infrastructure import BusinessSettingModel
from backend.modules.notifications.infrastructure import NotificationModel
from backend.modules.orders.application import (
    MatchActionDTO,
    OrderDTO,
    OrderMatchDTO,
    PaymentPromptDTO,
)
from backend.modules.orders.infrastructure.persistence.models import (
    OrderMatchModel,
    OrderModel,
    OrderStatusHistoryModel,
)
from backend.modules.payments.infrastructure import PaymentModel
from backend.modules.performers.infrastructure import PerformerModel


class SqlAlchemyMatchingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_available_pool_orders(
        self,
        *,
        performer_id: UUID,
        limit: int,
    ) -> tuple[OrderDTO, ...]:
        performer = await self._session.get(PerformerModel, performer_id)
        if performer is None or performer.status != "active":
            raise NotFoundError("Performer not found")
        now = utc_now()
        result = await self._session.execute(
            select(OrderModel)
            .where(
                OrderModel.matching_mode == "pool",
                OrderModel.status == "searching",
                OrderModel.matching_deadline_at > now,
            )
            .order_by(OrderModel.start_at)
            .limit(limit),
        )
        orders: list[OrderDTO] = []
        availability = SqlAlchemyAvailabilityRepository(self._session)
        for order in result.scalars():
            check = await availability.check(
                performer_id=performer_id,
                service_id=order.service_id,
                starts_at=order.start_at,
                ends_at=order.end_at,
            )
            if check.is_available:
                orders.append(_order_to_dto(order))
        return tuple(orders)

    async def create_pool_response(
        self,
        *,
        order_id: UUID,
        performer_id: UUID,
    ) -> OrderMatchDTO:
        order = await self._lock_order(order_id)
        performer = await self._lock_performer(performer_id)
        now = utc_now()
        if order.matching_mode != "pool" or order.status != "searching":
            raise ConflictError("Order is not accepting pool responses")
        if order.matching_deadline_at <= now:
            raise ConflictError("Order matching deadline has passed")
        if performer.status != "active" or not performer.is_accepting_orders:
            raise ValidationError("Performer cannot respond to orders")
        await self._ensure_pool_response_limit(order.id)
        check = await SqlAlchemyAvailabilityRepository(self._session).check(
            performer_id=performer.id,
            service_id=order.service_id,
            starts_at=order.start_at,
            ends_at=order.end_at,
        )
        if not check.is_available:
            raise ConflictError("Performer is not available")
        response_window = await self._integer_setting("pool_response_window_minutes")
        payment_window = await self._integer_setting("payment_window_minutes")
        close_before_start = await self._integer_setting(
            "payment_close_before_start_minutes",
        )
        response_expires_at = min(
            now + timedelta(minutes=response_window),
            order.start_at - timedelta(minutes=payment_window + close_before_start),
        )
        if response_expires_at <= now:
            raise ConflictError("Order response window has closed")
        match = OrderMatchModel(
            order_id=order.id,
            performer_id=performer.id,
            source="pool",
            status="active",
            starts_at=order.start_at,
            ends_at=order.end_at,
            response_expires_at=response_expires_at,
            responded_at=now,
        )
        self._session.add(match)
        await self._add_notification(
            recipient_type="customer",
            customer_id=order.customer_id,
            notification_type="pool_response_created",
            entity_type="order_match",
            entity_id=match.id,
            payload={"order_id": str(order.id), "match_id": str(match.id)},
            deduplication_key=f"pool-response-created:{match.id}",
        )
        await self._session.flush()
        return _match_to_dto(match)

    async def list_order_matches(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> tuple[OrderMatchDTO, ...]:
        order = await self._get_customer_order(order_id, customer_id)
        result = await self._session.execute(
            select(OrderMatchModel)
            .where(OrderMatchModel.order_id == order.id)
            .order_by(OrderMatchModel.created_at),
        )
        return tuple(_match_to_dto(match) for match in result.scalars())

    async def reject_pool_response(
        self,
        *,
        match_id: UUID,
        customer_id: UUID,
    ) -> OrderMatchDTO:
        match = await self._lock_match(match_id)
        await self._get_customer_order(match.order_id, customer_id, for_update=True)
        if match.source != "pool" or match.status != "active":
            raise ConflictError("Pool response is not active")
        now = utc_now()
        match.status = "rejected"
        match.closed_at = now
        match.close_reason = "customer_rejected"
        await self._add_notification(
            recipient_type="performer",
            performer_id=match.performer_id,
            notification_type="pool_response_rejected",
            entity_type="order_match",
            entity_id=match.id,
            payload={"order_id": str(match.order_id), "match_id": str(match.id)},
            deduplication_key=f"pool-response-rejected:{match.id}",
        )
        await self._session.flush()
        return _match_to_dto(match)

    async def accept_direct(
        self,
        *,
        match_id: UUID,
        performer_id: UUID,
    ) -> MatchActionDTO:
        match_probe = await self._get_match(match_id)
        if match_probe.performer_id != performer_id:
            raise NotFoundError("Direct match not found")
        order = await self._lock_order(match_probe.order_id)
        await self._lock_performer(performer_id)
        match = await self._lock_match(match_id)
        if match.source != "direct" or match.status != "pending":
            raise ConflictError("Direct invitation is not pending")
        return await self._select_match(
            order=order,
            match=match,
            close_other_pool_matches=False,
            notification_type="direct_accepted",
        )

    async def reject_direct(
        self,
        *,
        match_id: UUID,
        performer_id: UUID,
    ) -> OrderMatchDTO:
        match = await self._lock_match(match_id)
        if match.performer_id != performer_id:
            raise NotFoundError("Direct match not found")
        if match.source != "direct" or match.status != "pending":
            raise ConflictError("Direct invitation is not pending")
        now = utc_now()
        match.status = "rejected"
        match.responded_at = now
        match.closed_at = now
        match.close_reason = "performer_rejected"
        await self._add_notification(
            recipient_type="customer",
            customer_id=(await self._get_order(match.order_id)).customer_id,
            notification_type="direct_rejected",
            entity_type="order_match",
            entity_id=match.id,
            payload={"order_id": str(match.order_id), "match_id": str(match.id)},
            deduplication_key=f"direct-rejected:{match.id}",
        )
        await self._session.flush()
        return _match_to_dto(match)

    async def select_pool_response(
        self,
        *,
        match_id: UUID,
        customer_id: UUID,
    ) -> MatchActionDTO:
        match_probe = await self._get_match(match_id)
        order = await self._get_customer_order(
            match_probe.order_id,
            customer_id,
            for_update=True,
        )
        await self._lock_performer(match_probe.performer_id)
        match = await self._lock_match(match_id)
        if match.source != "pool" or match.status != "active":
            raise ConflictError("Pool response is not active")
        return await self._select_match(
            order=order,
            match=match,
            close_other_pool_matches=True,
            notification_type="pool_response_selected",
        )

    async def _select_match(
        self,
        *,
        order: OrderModel,
        match: OrderMatchModel,
        close_other_pool_matches: bool,
        notification_type: str,
    ) -> MatchActionDTO:
        now = utc_now()
        if order.status != "searching":
            raise ConflictError("Order is not searching")
        if order.matching_deadline_at <= now:
            raise ConflictError("Order matching deadline has passed")
        if match.response_expires_at <= now:
            raise ConflictError("Match response deadline has passed")
        check = await SqlAlchemyAvailabilityRepository(self._session).check(
            performer_id=match.performer_id,
            service_id=order.service_id,
            starts_at=order.start_at,
            ends_at=order.end_at,
            exclude_order_id=order.id,
            exclude_match_id=match.id,
        )
        if not check.is_available:
            raise ConflictError("Performer is not available")
        performer = await self._lock_performer(match.performer_id)
        if order.location_source == "performer_address":
            if performer.current_address_id is None:
                raise ValidationError("Performer work address is required")
            order.address_id = performer.current_address_id
        payment = await self._create_payment_attempt(order, match.performer_id)
        match.status = "selected"
        match.responded_at = match.responded_at or now
        match.selected_at = now
        order.status = "waiting_payment"
        order.selected_performer_id = match.performer_id
        order.selected_match_id = match.id
        order.active_payment_id = payment.id
        order.payment_deadline_at = payment.expires_at
        self._session.add(
            OrderStatusHistoryModel(
                order_id=order.id,
                from_status="searching",
                to_status="waiting_payment",
                actor_type="system",
                actor_id=None,
                reason=notification_type,
            ),
        )
        if close_other_pool_matches:
            await self._close_other_pool_matches(order.id, match.id, now)
        await self._add_notification(
            recipient_type="customer",
            customer_id=order.customer_id,
            notification_type=notification_type,
            entity_type="order_match",
            entity_id=match.id,
            payload={
                "order_id": str(order.id),
                "match_id": str(match.id),
                "payment_id": str(payment.id),
            },
            deduplication_key=f"{notification_type}:customer:{match.id}",
        )
        await self._add_notification(
            recipient_type="performer",
            performer_id=match.performer_id,
            notification_type=notification_type,
            entity_type="order_match",
            entity_id=match.id,
            payload={"order_id": str(order.id), "match_id": str(match.id)},
            deduplication_key=f"{notification_type}:performer:{match.id}",
        )
        await self._session.flush()
        return MatchActionDTO(
            order=_order_to_dto(order),
            match=_match_to_dto(match),
            payment=_payment_to_dto(payment),
        )

    async def _create_payment_attempt(
        self,
        order: OrderModel,
        performer_id: UUID,
    ) -> PaymentModel:
        now = utc_now()
        payment_window = await self._integer_setting("payment_window_minutes")
        close_before_start = await self._integer_setting(
            "payment_close_before_start_minutes",
        )
        expires_at = min(
            now + timedelta(minutes=payment_window),
            order.start_at - timedelta(minutes=close_before_start),
        )
        if expires_at <= now:
            raise ConflictError("Payment window has closed")
        attempt_number = await self._next_payment_attempt_number(order.id)
        payment = PaymentModel(
            order_id=order.id,
            performer_id=performer_id,
            attempt_number=attempt_number,
            provider="tbank_test",
            idempotency_key=f"payment:{order.id}:{attempt_number}",
            amount=order.total_amount,
            status="created",
            confirmation_url=None,
            expires_at=expires_at,
        )
        self._session.add(payment)
        await self._session.flush()
        return payment

    async def _next_payment_attempt_number(self, order_id: UUID) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(PaymentModel.attempt_number), 0)).where(
                PaymentModel.order_id == order_id,
            ),
        )
        return int(result.scalar_one()) + 1

    async def _close_other_pool_matches(
        self,
        order_id: UUID,
        selected_match_id: UUID,
        now: datetime,
    ) -> None:
        result = await self._session.execute(
            select(OrderMatchModel)
            .where(
                OrderMatchModel.order_id == order_id,
                OrderMatchModel.source == "pool",
                OrderMatchModel.status == "active",
                OrderMatchModel.id != selected_match_id,
            )
            .with_for_update(),
        )
        for match in result.scalars():
            match.status = "rejected"
            match.closed_at = now
            match.close_reason = "customer_selected_other"

    async def _ensure_pool_response_limit(self, order_id: UUID) -> None:
        max_responses = await self._integer_setting("max_active_pool_responses")
        result = await self._session.execute(
            select(func.count())
            .select_from(OrderMatchModel)
            .where(
                OrderMatchModel.order_id == order_id,
                OrderMatchModel.source == "pool",
                OrderMatchModel.status == "active",
            ),
        )
        if int(result.scalar_one()) >= max_responses:
            raise ConflictError("Pool response limit reached")

    async def _integer_setting(self, key: str) -> int:
        result = await self._session.execute(
            select(BusinessSettingModel.value).where(BusinessSettingModel.key == key),
        )
        value = result.scalar_one_or_none()
        if value is None:
            raise ValidationError(f"Business setting {key} is not configured")
        return int(value)

    async def _add_notification(
        self,
        *,
        recipient_type: str,
        notification_type: str,
        entity_type: str,
        entity_id: UUID,
        payload: dict[str, str],
        deduplication_key: str,
        customer_id: UUID | None = None,
        performer_id: UUID | None = None,
    ) -> None:
        now = utc_now()
        self._session.add(
            NotificationModel(
                recipient_type=recipient_type,
                customer_id=customer_id,
                performer_id=performer_id,
                admin_id=None,
                channel="telegram",
                type=notification_type,
                entity_type=entity_type,
                entity_id=entity_id,
                payload=payload,
                deduplication_key=deduplication_key,
                status="pending",
                attempts=0,
                scheduled_at=now,
                delete_after=now + timedelta(days=30),
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

    async def _get_order(self, order_id: UUID) -> OrderModel:
        order = await self._session.get(OrderModel, order_id)
        if order is None:
            raise NotFoundError("Order not found")
        return order

    async def _get_customer_order(
        self,
        order_id: UUID,
        customer_id: UUID,
        *,
        for_update: bool = False,
    ) -> OrderModel:
        statement = select(OrderModel).where(
            OrderModel.id == order_id,
            OrderModel.customer_id == customer_id,
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.execute(statement)
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

    async def _get_match(self, match_id: UUID) -> OrderMatchModel:
        match = await self._session.get(OrderMatchModel, match_id)
        if match is None:
            raise NotFoundError("Order match not found")
        return match

    async def _lock_match(self, match_id: UUID) -> OrderMatchModel:
        result = await self._session.execute(
            select(OrderMatchModel)
            .where(OrderMatchModel.id == match_id)
            .with_for_update(),
        )
        match = result.scalar_one_or_none()
        if match is None:
            raise NotFoundError("Order match not found")
        return match


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


def _match_to_dto(model: OrderMatchModel) -> OrderMatchDTO:
    return OrderMatchDTO(
        id=model.id,
        order_id=model.order_id,
        performer_id=model.performer_id,
        source=model.source,
        status=model.status,
        starts_at=model.starts_at,
        ends_at=model.ends_at,
        response_expires_at=model.response_expires_at,
        selected_at=model.selected_at,
        closed_at=model.closed_at,
        close_reason=model.close_reason,
    )


def _payment_to_dto(model: PaymentModel) -> PaymentPromptDTO:
    return PaymentPromptDTO(
        payment_id=model.id,
        confirmation_url=model.confirmation_url,
        expires_at=model.expires_at,
    )

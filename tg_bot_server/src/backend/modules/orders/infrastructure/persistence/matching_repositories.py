from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import exists, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import to_timezone, utc_now
from backend.common.domain import ConflictError, NotFoundError, ValidationError
from backend.modules.addresses.infrastructure import AddressModel
from backend.modules.availability.infrastructure import SqlAlchemyAvailabilityRepository
from backend.modules.catalog.infrastructure import (
    BusinessSettingModel,
    CityModel,
    DistrictModel,
    ServiceCategoryModel,
    ServiceModel,
)
from backend.modules.customers.infrastructure import CustomerModel
from backend.modules.geo.application import haversine_distance_km
from backend.modules.notifications.infrastructure import NotificationModel
from backend.modules.orders.application import (
    MatchActionDTO,
    OrderDTO,
    OrderMatchDTO,
    PaymentPromptDTO,
)
from backend.modules.orders.infrastructure.persistence.models import (
    OrderAddressSnapshotModel,
    OrderCareObjectModel,
    OrderMatchModel,
    OrderModel,
    OrderStatusHistoryModel,
)
from backend.modules.payments.infrastructure import PaymentModel
from backend.modules.performers.infrastructure import (
    PerformerCalendarOverrideModel,
    PerformerModel,
    PerformerScheduleModel,
    PerformerServiceModel,
)


class SqlAlchemyMatchingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_available_pool_orders(
        self,
        *,
        performer_id: UUID,
        limit: int,
        category_code: str | None = None,
    ) -> tuple[OrderDTO, ...]:
        performer = await self._session.get(PerformerModel, performer_id)
        if performer is None or performer.status != "active":
            raise NotFoundError("Performer not found")
        if not performer.is_accepting_orders:
            raise ValidationError("Performer is not accepting orders")
        if performer.current_address_id is None:
            raise ValidationError("Performer work address is required")
        has_schedule = await self._session.scalar(
            select(PerformerScheduleModel.id).where(
                PerformerScheduleModel.performer_id == performer_id,
                PerformerScheduleModel.is_active.is_(True),
            )
        )
        if has_schedule is None:
            raise ValidationError("Performer schedule is not configured")
        has_enabled_service = await self._session.scalar(
            select(PerformerServiceModel.id).where(
                PerformerServiceModel.performer_id == performer_id,
                PerformerServiceModel.is_approved.is_(True),
                PerformerServiceModel.is_enabled.is_(True),
            )
        )
        if has_enabled_service is None:
            raise ValidationError("Performer has no enabled services")
        now = utc_now()
        is_currently_unavailable = await self._session.scalar(
            select(PerformerCalendarOverrideModel.id).where(
                PerformerCalendarOverrideModel.performer_id == performer_id,
                PerformerCalendarOverrideModel.override_type == "unavailable",
                PerformerCalendarOverrideModel.is_active.is_(True),
                PerformerCalendarOverrideModel.starts_at <= now,
                PerformerCalendarOverrideModel.ends_at > now,
            )
        )
        if is_currently_unavailable is not None:
            raise ValidationError("Performer is currently unavailable")
        result = await self._session.execute(
            select(OrderModel)
            .join(ServiceModel, ServiceModel.id == OrderModel.service_id)
            .join(
                ServiceCategoryModel,
                ServiceCategoryModel.id == ServiceModel.category_id,
            )
            .where(
                OrderModel.matching_mode == "pool",
                OrderModel.status == "searching",
                OrderModel.matching_deadline_at > now,
                ~exists(
                    select(OrderMatchModel.id).where(
                        OrderMatchModel.order_id == OrderModel.id,
                        OrderMatchModel.performer_id == performer_id,
                    ),
                ),
            )
            .where(
                ServiceCategoryModel.code == category_code
                if category_code is not None
                else true(),
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
                snapshot = await self._session.scalar(
                    select(OrderAddressSnapshotModel).where(
                        OrderAddressSnapshotModel.order_id == order.id,
                    )
                )
                performer_address = await self._session.get(
                    AddressModel,
                    performer.current_address_id,
                )
                distance_km = None
                if (
                    snapshot is not None
                    and performer_address is not None
                    and snapshot.latitude is not None
                    and snapshot.longitude is not None
                    and performer_address.latitude is not None
                    and performer_address.longitude is not None
                ):
                    distance_km = haversine_distance_km(
                        first_latitude=performer_address.latitude,
                        first_longitude=performer_address.longitude,
                        second_latitude=snapshot.latitude,
                        second_longitude=snapshot.longitude,
                    )
                orders.append(await self._order_to_dto(order, distance_km=distance_km))
        return tuple(orders)

    async def list_performer_responses(
        self,
        *,
        performer_id: UUID,
        group: str,
    ) -> tuple[OrderMatchDTO, ...]:
        statuses = {
            "active": ("active",),
            "selected": ("selected",),
            "closed": ("closed", "rejected", "cancelled", "expired"),
        }.get(group)
        if group == "direct":
            statuses = ("pending",)
        elif statuses is None:
            raise ValidationError("Invalid response group")
        statement = (
            select(OrderMatchModel, OrderModel)
            .join(OrderModel, OrderModel.id == OrderMatchModel.order_id)
            .where(
                OrderMatchModel.performer_id == performer_id,
                OrderMatchModel.status.in_(statuses),
            )
            .order_by(OrderMatchModel.created_at.desc())
        )
        if group == "direct":
            statement = statement.where(OrderMatchModel.source == "direct")
        result = await self._session.execute(statement)
        matches: list[OrderMatchDTO] = []
        for match, order in result.all():
            matches.append(
                _match_to_dto(
                    match,
                    await self._order_timezone(order),
                    order=order,
                    distance_km=await self._distance_for_match(
                        order,
                        match.performer_id,
                    ),
                )
            )
        return tuple(matches)

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
        if performer.current_address_id is None:
            raise ValidationError("Performer work address is required")
        await self._ensure_no_historical_match(order.id, performer.id)
        await self._lock_overlapping_resources(
            performer_id=performer.id,
            starts_at=order.start_at,
            ends_at=order.end_at,
        )
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
        await self._session.flush()
        timezone = await self._order_timezone(order)
        distance_km = await self._distance_for_match(order, performer_id)
        payload = {
            "order_id": str(order.id),
            "match_id": str(match.id),
            "service_name": order.service_name,
            "start_at": to_timezone(order.start_at, timezone).isoformat(),
            "end_at": to_timezone(order.end_at, timezone).isoformat(),
            "response_expires_at": to_timezone(
                match.response_expires_at,
                timezone,
            ).isoformat(),
            "objects_count": str(order.objects_count),
            "performer_amount": str(order.performer_amount),
            "customer_comment": order.customer_comment or "",
        }
        if distance_km is not None:
            payload["distance_km"] = str(distance_km)
        await self._add_notification(
            recipient_type="customer",
            customer_id=order.customer_id,
            notification_type="pool_response_created",
            entity_type="order_match",
            entity_id=match.id,
            payload=payload,
            deduplication_key=f"pool-response-created:{match.id}",
        )
        return _match_to_dto(match, await self._order_timezone(order), order=order)

    async def invite_direct_performer(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
        performer_id: UUID,
    ) -> OrderMatchDTO:
        order = await self._get_customer_order(order_id, customer_id, for_update=True)
        performer = await self._lock_performer(performer_id)
        now = utc_now()
        if order.matching_mode != "direct" or order.status != "searching":
            raise ConflictError("Order is not ready for direct invitation")
        if await self._active_direct_match(order.id) is not None:
            raise ConflictError("Direct invitation is already pending")
        await self._ensure_no_historical_match(order.id, performer_id)
        if performer.status != "active" or not performer.is_accepting_orders:
            raise ValidationError("Performer cannot receive direct order")
        if performer.current_address_id is None:
            raise ValidationError("Performer work address is required")
        if not await self._performer_can_receive_order(order, performer_id):
            raise ConflictError("Performer is not suitable for direct order")
        await self._lock_overlapping_resources(
            performer_id=performer_id,
            starts_at=order.start_at,
            ends_at=order.end_at,
        )
        check = await SqlAlchemyAvailabilityRepository(self._session).check(
            performer_id=performer_id,
            service_id=order.service_id,
            starts_at=order.start_at,
            ends_at=order.end_at,
        )
        if not check.is_available:
            raise ConflictError("Performer is not available")
        response_window = await self._integer_setting("direct_response_window_minutes")
        match = OrderMatchModel(
            order_id=order.id,
            performer_id=performer_id,
            source="direct",
            status="pending",
            starts_at=order.start_at,
            ends_at=order.end_at,
            response_expires_at=now + timedelta(minutes=response_window),
        )
        self._session.add(match)
        await self._session.flush()
        timezone = await self._order_timezone(order)
        distance_km = await self._distance_for_match(order, performer_id)
        payload = {
            "order_id": str(order.id),
            "match_id": str(match.id),
            "service_name": order.service_name,
            "start_at": to_timezone(order.start_at, timezone).isoformat(),
            "end_at": to_timezone(order.end_at, timezone).isoformat(),
            "response_expires_at": to_timezone(
                match.response_expires_at,
                timezone,
            ).isoformat(),
            "objects_count": str(order.objects_count),
            "performer_amount": str(order.performer_amount),
            "customer_comment": order.customer_comment or "",
        }
        if distance_km is not None:
            payload["distance_km"] = str(distance_km)
        await self._add_notification(
            recipient_type="performer",
            performer_id=performer_id,
            notification_type="direct_invitation_created",
            entity_type="order_match",
            entity_id=match.id,
            payload=payload,
            deduplication_key=f"direct-invitation-created:{match.id}",
        )
        return _match_to_dto(match, await self._order_timezone(order), order=order)

    async def publish_pool(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> OrderDTO:
        order = await self._get_customer_order(order_id, customer_id, for_update=True)
        if order.status != "searching":
            raise ConflictError("Order is not ready for pool publication")
        if await self._active_direct_match(order.id) is not None:
            raise ConflictError("Direct invitation is still pending")
        order.matching_mode = "pool"
        await self._session.flush()
        await self._notify_nearby_performers(order)
        return await self._order_to_dto(order)

    async def notify_nearby_performers(self, *, order_id: UUID) -> None:
        order = await self._session.get(OrderModel, order_id)
        if order is None:
            raise NotFoundError("Order not found")
        await self._notify_nearby_performers(order)

    async def _notify_nearby_performers(self, order: OrderModel) -> None:
        city_row = await self._session.execute(
            select(CustomerModel.city_id, CityModel.timezone)
            .join(CityModel, CityModel.id == CustomerModel.city_id)
            .where(CustomerModel.id == order.customer_id),
        )
        customer_city = city_row.one_or_none()
        if customer_city is None:
            return
        city_id, timezone = customer_city
        care_object_ids = tuple(
            care_object_id
            for care_object_id in await self._session.scalars(
                select(OrderCareObjectModel.care_object_id).where(
                    OrderCareObjectModel.order_id == order.id,
                ),
            )
            if care_object_id is not None
        )
        candidates = await SqlAlchemyAvailabilityRepository(
            self._session,
        ).find_suitable_performers(
            city_id=city_id,
            service_id=order.service_id,
            starts_at=order.start_at,
            ends_at=order.end_at,
            objects_count=order.objects_count,
            care_object_ids=care_object_ids,
            address_id=order.address_id,
            limit=10,
        )
        enabled_ids = set(
            await self._session.scalars(
                select(PerformerModel.id).where(
                    PerformerModel.id.in_(
                        tuple(item.performer_id for item in candidates)
                    ),
                    PerformerModel.is_nearby_order_notifications_enabled.is_(True),
                ),
            )
        )
        for candidate in candidates:
            if candidate.performer_id not in enabled_ids:
                continue
            payload = {
                "order_id": str(order.id),
                "service_name": order.service_name,
                "start_at": order.start_at.isoformat(),
                "end_at": order.end_at.isoformat(),
                "objects_count": str(order.objects_count),
                "total_amount": str(order.total_amount),
                "timezone": timezone,
            }
            if candidate.distance_km is not None:
                payload["distance_km"] = str(candidate.distance_km)
            await self._add_notification(
                recipient_type="performer",
                performer_id=candidate.performer_id,
                notification_type="pool_order_available",
                entity_type="order",
                entity_id=order.id,
                payload=payload,
                deduplication_key=(
                    f"pool-order-available:{order.id}:{candidate.performer_id}"
                ),
            )

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
        timezone = await self._order_timezone(order)
        return tuple(_match_to_dto(match, timezone) for match in result.scalars())

    async def reject_pool_response(
        self,
        *,
        match_id: UUID,
        customer_id: UUID,
    ) -> OrderMatchDTO:
        match_probe = await self._get_match(match_id)
        order = await self._get_customer_order(
            match_probe.order_id,
            customer_id,
            for_update=True,
        )
        match = await self._lock_match(match_id)
        if (
            match.source != "pool"
            or match.status != "active"
            or order.status != "searching"
        ):
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
        return _match_to_dto(match, await self._order_timezone(match.order_id))

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
        match_probe = await self._get_match(match_id)
        if match_probe.performer_id != performer_id:
            raise NotFoundError("Direct match not found")
        order = await self._lock_order(match_probe.order_id)
        await self._lock_performer(performer_id)
        match = await self._lock_match(match_id)
        if match.performer_id != performer_id:
            raise NotFoundError("Direct match not found")
        if (
            match.source != "direct"
            or match.status != "pending"
            or order.status != "searching"
        ):
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
        return _match_to_dto(match, await self._order_timezone(match.order_id))

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
        await self._lock_overlapping_resources(
            performer_id=match.performer_id,
            starts_at=order.start_at,
            ends_at=order.end_at,
            exclude_order_id=order.id,
            exclude_match_id=match.id,
        )
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
            await self._save_address_snapshot(order.id, order.address_id)
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
        timezone = await self._order_timezone(order)
        return MatchActionDTO(
            order=_order_to_dto(order, timezone),
            match=_match_to_dto(match, timezone),
            payment=_payment_to_dto(payment, timezone),
        )

    async def _save_address_snapshot(
        self,
        order_id: UUID,
        address_id: UUID,
    ) -> None:
        result = await self._session.execute(
            select(AddressModel, CityModel.name, DistrictModel.name)
            .join(CityModel, CityModel.id == AddressModel.city_id)
            .outerjoin(DistrictModel, DistrictModel.id == AddressModel.district_id)
            .where(
                AddressModel.id == address_id,
                AddressModel.deleted_at.is_(None),
            ),
        )
        row = result.one_or_none()
        if row is None:
            raise ValidationError("Performer work address is unavailable")
        address, city_name, district_name = row
        snapshot = await self._session.scalar(
            select(OrderAddressSnapshotModel).where(
                OrderAddressSnapshotModel.order_id == order_id,
            ),
        )
        if snapshot is None:
            snapshot = OrderAddressSnapshotModel(
                order_id=order_id,
                source_address_id=address.id,
                city_name=city_name,
                district_name=district_name,
                address_text=address.address_text,
                fias_id=address.fias_id,
                latitude=address.latitude,
                longitude=address.longitude,
                geocoding_provider=address.geocoding_provider,
                geocoding_quality=address.geocoding_quality,
                entrance=address.entrance,
                floor=address.floor,
                apartment=address.apartment,
                comment=address.comment,
            )
            self._session.add(snapshot)
            return
        snapshot.source_address_id = address.id
        snapshot.city_name = city_name
        snapshot.district_name = district_name
        snapshot.address_text = address.address_text
        snapshot.fias_id = address.fias_id
        snapshot.latitude = address.latitude
        snapshot.longitude = address.longitude
        snapshot.geocoding_provider = address.geocoding_provider
        snapshot.geocoding_quality = address.geocoding_quality
        snapshot.entrance = address.entrance
        snapshot.floor = address.floor
        snapshot.apartment = address.apartment
        snapshot.comment = address.comment

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

    async def _ensure_no_historical_match(
        self,
        order_id: UUID,
        performer_id: UUID,
    ) -> None:
        result = await self._session.execute(
            select(OrderMatchModel.id).where(
                OrderMatchModel.order_id == order_id,
                OrderMatchModel.performer_id == performer_id,
            ),
        )
        if result.scalar_one_or_none() is not None:
            raise ConflictError("Performer already responded to order")

    async def _active_direct_match(
        self,
        order_id: UUID,
    ) -> OrderMatchModel | None:
        result = await self._session.execute(
            select(OrderMatchModel)
            .where(
                OrderMatchModel.order_id == order_id,
                OrderMatchModel.source == "direct",
                OrderMatchModel.status == "pending",
            )
            .with_for_update(),
        )
        return result.scalar_one_or_none()

    async def _performer_can_receive_order(
        self,
        order: OrderModel,
        performer_id: UUID,
    ) -> bool:
        result = await self._session.execute(
            select(PerformerServiceModel).where(
                PerformerServiceModel.performer_id == performer_id,
                PerformerServiceModel.service_id == order.service_id,
                PerformerServiceModel.is_approved.is_(True),
                PerformerServiceModel.is_enabled.is_(True),
                PerformerServiceModel.performer_max_objects >= order.objects_count,
            ),
        )
        return result.scalar_one_or_none() is not None

    async def _lock_overlapping_resources(
        self,
        *,
        performer_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        exclude_order_id: UUID | None = None,
        exclude_match_id: UUID | None = None,
    ) -> None:
        match_statement = (
            select(OrderMatchModel)
            .where(
                OrderMatchModel.performer_id == performer_id,
                OrderMatchModel.status.in_(("active", "selected")),
                OrderMatchModel.starts_at < ends_at,
                OrderMatchModel.ends_at > starts_at,
            )
            .with_for_update()
        )
        if exclude_match_id is not None:
            match_statement = match_statement.where(
                OrderMatchModel.id != exclude_match_id,
            )
        await self._session.execute(match_statement)
        order_statement = (
            select(OrderModel)
            .where(
                OrderModel.selected_performer_id == performer_id,
                OrderModel.status == "confirmed",
                OrderModel.start_at < ends_at,
                OrderModel.end_at > starts_at,
            )
            .with_for_update()
        )
        if exclude_order_id is not None:
            order_statement = order_statement.where(OrderModel.id != exclude_order_id)
        await self._session.execute(order_statement)

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
            CustomerModel.status == "active",
            CustomerModel.deleted_at.is_(None),
        )
        statement = statement.join(
            CustomerModel, CustomerModel.id == OrderModel.customer_id
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

    async def _distance_for_match(
        self,
        order: OrderModel,
        performer_id: UUID,
    ) -> Decimal | None:
        if order.address_id is None:
            return None
        snapshot = await self._session.scalar(
            select(OrderAddressSnapshotModel).where(
                OrderAddressSnapshotModel.order_id == order.id,
            ),
        )
        performer = await self._session.get(PerformerModel, performer_id)
        if (
            snapshot is None
            or performer is None
            or performer.current_address_id is None
        ):
            return None
        performer_address = await self._session.get(
            AddressModel,
            performer.current_address_id,
        )
        if (
            performer_address is None
            or snapshot.latitude is None
            or snapshot.longitude is None
            or performer_address.latitude is None
            or performer_address.longitude is None
        ):
            return None
        return haversine_distance_km(
            first_latitude=performer_address.latitude,
            first_longitude=performer_address.longitude,
            second_latitude=snapshot.latitude,
            second_longitude=snapshot.longitude,
        )

    async def _order_to_dto(
        self,
        model: OrderModel,
        *,
        distance_km: Decimal | None = None,
    ) -> OrderDTO:
        return _order_to_dto(
            model,
            await self._order_timezone(model),
            distance_km=distance_km,
        )

    async def _order_timezone(self, order: OrderModel | UUID) -> str:
        if isinstance(order, OrderModel):
            customer_id = order.customer_id
        else:
            result = await self._session.execute(
                select(OrderModel.customer_id).where(OrderModel.id == order),
            )
            customer_id = result.scalar_one_or_none()
        if customer_id is None:
            raise ValidationError("Order customer is required")
        timezone_result = await self._session.execute(
            select(CityModel.timezone)
            .join(CustomerModel, CustomerModel.city_id == CityModel.id)
            .where(
                CustomerModel.id == customer_id,
                CustomerModel.status == "active",
                CustomerModel.deleted_at.is_(None),
                CityModel.is_active.is_(True),
            ),
        )
        timezone = timezone_result.scalar_one_or_none()
        if timezone is None:
            raise ValidationError("Order customer city is invalid")
        return timezone


def _order_to_dto(
    model: OrderModel,
    timezone: str,
    *,
    distance_km: Decimal | None = None,
) -> OrderDTO:
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
        report_photo_consent=model.report_photo_consent,
        distance_km=distance_km,
    )


def _match_to_dto(
    model: OrderMatchModel,
    timezone: str,
    *,
    order: OrderModel | None = None,
    distance_km: Decimal | None = None,
) -> OrderMatchDTO:
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
        timezone=timezone,
        service_name=order.service_name if order is not None else None,
        total_amount=order.total_amount if order is not None else None,
        distance_km=distance_km,
        customer_comment=order.customer_comment if order is not None else None,
    )


def _payment_to_dto(model: PaymentModel, timezone: str) -> PaymentPromptDTO:
    return PaymentPromptDTO(
        payment_id=model.id,
        confirmation_url=model.confirmation_url,
        expires_at=model.expires_at,
        timezone=timezone,
    )

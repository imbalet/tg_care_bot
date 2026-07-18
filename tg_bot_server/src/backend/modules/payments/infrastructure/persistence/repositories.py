from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import new_uuid, utc_now
from backend.common.domain import ConflictError, ValidationError
from backend.modules.catalog.infrastructure import BusinessSettingModel
from backend.modules.customers.infrastructure import CustomerModel
from backend.modules.notifications.infrastructure import NotificationModel
from backend.modules.orders.infrastructure.persistence.models import (
    OrderMatchModel,
    OrderModel,
    OrderStatusHistoryModel,
)
from backend.modules.payments.application import (
    PaymentAttemptDTO,
    PaymentInitializationData,
    PaymentStatusDTO,
    PaymentWebhookCommand,
    PaymentWebhookResult,
    RefundDTO,
)
from backend.modules.payments.infrastructure.persistence.models import (
    PaymentModel,
    RefundModel,
)


class SqlAlchemyPaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_attempt_number(self, order_id: UUID) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(PaymentModel.attempt_number), 0)).where(
                PaymentModel.order_id == order_id,
            ),
        )
        return int(result.scalar_one()) + 1

    async def add(self, payment: PaymentModel) -> PaymentModel:
        self._session.add(payment)
        await self._session.flush()
        return payment

    async def get_initialization_data(
        self,
        payment_id: UUID,
    ) -> PaymentInitializationData | None:
        result = await self._session.execute(
            select(PaymentModel, OrderModel, CustomerModel)
            .join(OrderModel, OrderModel.id == PaymentModel.order_id)
            .join(CustomerModel, CustomerModel.id == OrderModel.customer_id)
            .where(PaymentModel.id == payment_id),
        )
        row = result.one_or_none()
        if row is None:
            return None
        payment, order, customer = row
        return PaymentInitializationData(
            payment=_payment_to_dto(payment),
            customer_phone=customer.phone,
            customer_name=customer.full_name,
            service_name=order.service_name,
        )

    async def mark_provider_initialized(
        self,
        *,
        payment_id: UUID,
        provider_payment_id: str,
        provider_deal_id: str | None,
        confirmation_url: str,
    ) -> None:
        payment = await self._session.get(PaymentModel, payment_id)
        if payment is None or payment.status != "created":
            return
        payment.provider_payment_id = provider_payment_id
        payment.provider_deal_id = provider_deal_id
        payment.confirmation_url = confirmation_url
        payment.status = "pending"
        payment.failure_code = None

    async def mark_provider_initialization_failed(
        self,
        *,
        payment_id: UUID,
        failure_code: str,
    ) -> None:
        payment = await self._session.get(PaymentModel, payment_id)
        if payment is None or payment.status != "created":
            return
        payment.failure_code = failure_code

    async def apply_successful_webhook(
        self,
        command: PaymentWebhookCommand,
    ) -> PaymentWebhookResult | None:
        payment_probe = await self._get_payment_by_provider_id(
            command.provider_payment_id,
        )
        if payment_probe is None:
            return None
        order = await self._lock_order(payment_probe.order_id)
        payment = await self._lock_payment(payment_probe.id)
        match = (
            await self._lock_match(order.selected_match_id)
            if order.selected_match_id is not None
            else None
        )
        if payment.status == "succeeded":
            return PaymentWebhookResult(
                payment_id=payment.id,
                order_id=order.id,
                status=payment.status,
                applied=payment.applied_at is not None,
                unapplied_reason=payment.unapplied_reason,
            )
        if payment.status == "succeeded_unapplied":
            return PaymentWebhookResult(
                payment_id=payment.id,
                order_id=order.id,
                status=payment.status,
                applied=False,
                unapplied_reason=payment.unapplied_reason,
            )
        payment.paid_at = command.paid_at
        unapplied_reason = _unapplied_reason(
            order=order,
            payment=payment,
            match=match,
            paid_amount=command.amount,
            paid_at=command.paid_at,
        )
        if unapplied_reason is not None:
            payment.status = "succeeded_unapplied"
            payment.unapplied_reason = unapplied_reason
            await self._session.flush()
            return PaymentWebhookResult(
                payment_id=payment.id,
                order_id=order.id,
                status=payment.status,
                applied=False,
                unapplied_reason=unapplied_reason,
            )
        now = utc_now()
        payment.status = "succeeded"
        payment.applied_at = now
        payment.unapplied_reason = None
        order.status = "confirmed"
        order.refund_policy_version_at_payment = await self._string_setting(
            "refund_policy_version",
        )
        order.partial_refund_percent_at_payment = await self._decimal_setting(
            "partial_refund_percent",
        )
        order.payout_status = "blocked"
        order.payout_amount = order.performer_amount
        order.payout_idempotency_key = f"payout:{order.id}"
        if match is not None:
            match.status = "confirmed"
            match.confirmed_at = now
        self._session.add(
            OrderStatusHistoryModel(
                order_id=order.id,
                from_status="waiting_payment",
                to_status="confirmed",
                actor_type="system",
                actor_id=None,
                reason="payment_webhook",
            ),
        )
        await self._add_notification(
            recipient_type="customer",
            customer_id=order.customer_id,
            notification_type="payment_confirmed",
            entity_type="order",
            entity_id=order.id,
            payload={"order_id": str(order.id), "payment_id": str(payment.id)},
            deduplication_key=f"payment-confirmed:customer:{payment.id}",
        )
        await self._add_notification(
            recipient_type="performer",
            performer_id=order.selected_performer_id,
            notification_type="payment_confirmed",
            entity_type="order",
            entity_id=order.id,
            payload={"order_id": str(order.id), "payment_id": str(payment.id)},
            deduplication_key=f"payment-confirmed:performer:{payment.id}",
        )
        await self._session.flush()
        return PaymentWebhookResult(
            payment_id=payment.id,
            order_id=order.id,
            status=payment.status,
            applied=True,
            unapplied_reason=None,
        )

    async def _get_payment_by_provider_id(
        self,
        provider_payment_id: str,
    ) -> PaymentModel | None:
        result = await self._session.execute(
            select(PaymentModel).where(
                PaymentModel.provider == "tbank_test",
                PaymentModel.provider_payment_id == provider_payment_id,
            ),
        )
        return result.scalar_one_or_none()

    async def _lock_order(self, order_id: UUID) -> OrderModel:
        result = await self._session.execute(
            select(OrderModel).where(OrderModel.id == order_id).with_for_update(),
        )
        return result.scalar_one()

    async def _lock_payment(self, payment_id: UUID) -> PaymentModel:
        result = await self._session.execute(
            select(PaymentModel).where(PaymentModel.id == payment_id).with_for_update(),
        )
        return result.scalar_one()

    async def _lock_match(self, match_id: UUID) -> OrderMatchModel | None:
        result = await self._session.execute(
            select(OrderMatchModel)
            .where(OrderMatchModel.id == match_id)
            .with_for_update(),
        )
        return result.scalar_one_or_none()

    async def _string_setting(self, key: str) -> str:
        value = await self._setting_value(key)
        return str(value)

    async def _decimal_setting(self, key: str) -> Decimal | None:
        value = await self._setting_value(key)
        return Decimal(str(value)) if value is not None else None

    async def _setting_value(self, key: str) -> object:
        result = await self._session.execute(
            select(BusinessSettingModel.value).where(BusinessSettingModel.key == key),
        )
        return result.scalar_one_or_none()

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
        if customer_id is None and performer_id is None:
            return
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

    async def create_manual_refund(
        self,
        *,
        payment_id: UUID,
        amount: Decimal,
        reason: str,
        admin_id: UUID,
    ) -> RefundDTO:
        payment = await self._lock_payment(payment_id)
        order = await self._lock_order(payment.order_id)
        if payment.status != "succeeded":
            raise ConflictError("Payment is not succeeded")
        if amount > payment.amount:
            raise ValidationError("Refund amount exceeds payment amount")
        refund_type = "full" if amount == payment.amount else "partial"
        idempotency_key = (
            f"manual-refund:{payment.id}:{admin_id}:{amount.quantize(Decimal('0.01'))}"
            f":{reason}"
        )
        existing = await self._get_refund_by_idempotency_key(idempotency_key)
        if existing is not None:
            return _refund_to_dto(existing)
        refund = RefundModel(
            id=new_uuid(),
            order_id=order.id,
            payment_id=payment.id,
            refund_type=refund_type,
            amount=amount,
            status="pending",
            reason=reason,
            created_by_admin_id=admin_id,
            idempotency_key=idempotency_key,
        )
        self._session.add(refund)
        await self._session.flush()
        return _refund_to_dto(refund)

    async def mark_refund_succeeded(
        self,
        *,
        refund_id: UUID,
        provider_refund_id: str,
    ) -> None:
        refund = await self._lock_refund(refund_id)
        if refund.status != "pending":
            return
        refund.status = "succeeded"
        refund.provider_refund_id = provider_refund_id
        refund.completed_at = utc_now()

    async def mark_refund_failed(self, *, refund_id: UUID) -> None:
        refund = await self._lock_refund(refund_id)
        if refund.status != "pending":
            return
        refund.status = "failed"

    async def _get_refund_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> RefundModel | None:
        result = await self._session.execute(
            select(RefundModel).where(
                RefundModel.idempotency_key == idempotency_key,
            ),
        )
        return result.scalar_one_or_none()

    async def _lock_refund(self, refund_id: UUID) -> RefundModel:
        result = await self._session.execute(
            select(RefundModel).where(RefundModel.id == refund_id).with_for_update(),
        )
        return result.scalar_one()

    async def get_customer_payment_status(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> PaymentStatusDTO | None:
        result = await self._session.execute(
            select(OrderModel, PaymentModel)
            .outerjoin(PaymentModel, PaymentModel.id == OrderModel.active_payment_id)
            .where(OrderModel.id == order_id, OrderModel.customer_id == customer_id),
        )
        row = result.one_or_none()
        if row is None:
            return None
        order, payment = row
        return PaymentStatusDTO(
            order_id=order.id,
            order_status=order.status,
            payment_id=payment.id if payment is not None else None,
            payment_status=payment.status if payment is not None else None,
            confirmation_url=payment.confirmation_url if payment is not None else None,
            expires_at=payment.expires_at if payment is not None else None,
        )


def _payment_to_dto(model: PaymentModel) -> PaymentAttemptDTO:
    return PaymentAttemptDTO(
        id=model.id,
        order_id=model.order_id,
        performer_id=model.performer_id,
        attempt_number=model.attempt_number,
        provider=model.provider,
        provider_payment_id=model.provider_payment_id,
        provider_deal_id=model.provider_deal_id,
        idempotency_key=model.idempotency_key,
        amount=model.amount,
        status=model.status,
        confirmation_url=model.confirmation_url,
        expires_at=model.expires_at,
    )


def _refund_to_dto(model: RefundModel) -> RefundDTO:
    return RefundDTO(
        id=model.id,
        order_id=model.order_id,
        payment_id=model.payment_id,
        refund_type=model.refund_type,
        amount=model.amount,
        status=model.status,
        reason=model.reason,
        provider_refund_id=model.provider_refund_id,
        idempotency_key=model.idempotency_key,
    )


def _unapplied_reason(
    *,
    order: OrderModel,
    payment: PaymentModel,
    match: OrderMatchModel | None,
    paid_amount: Decimal,
    paid_at: datetime,
) -> str | None:
    if order.status != "waiting_payment":
        return "order_status_mismatch"
    if order.active_payment_id != payment.id:
        return "payment_is_not_active"
    if order.selected_performer_id != payment.performer_id:
        return "performer_mismatch"
    if match is None or match.id != order.selected_match_id:
        return "match_is_not_selected"
    if match.status != "selected":
        return "match_status_mismatch"
    if paid_amount != order.total_amount:
        return "amount_mismatch"
    if paid_at > payment.expires_at:
        return "payment_expired"
    return None

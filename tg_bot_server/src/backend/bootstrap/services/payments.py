import logging

from sqlalchemy import select

from backend.modules.orders.infrastructure.exports import OrderModel
from backend.modules.support.infrastructure import DisputeModel

from ._shared import (
    UUID,
    AdminAuditLogModel,
    Any,
    ApplyPaymentWebhookUseCase,
    CreateManualRefundCommand,
    CreateManualRefundUseCase,
    GetCustomerPaymentStatusCommand,
    GetCustomerPaymentStatusUseCase,
    MarkManualPayoutCommand,
    MarkManualPayoutUseCase,
    NotFoundError,
    PaymentGatewayInitCommand,
    PaymentGatewayRefundCommand,
    PaymentWebhookCommand,
    RetryCustomerPaymentCommand,
    RetryCustomerPaymentUseCase,
    RetryPaymentOperationCommand,
    RetryPaymentOperationUseCase,
    SqlAlchemyPaymentRepository,
    ValidationError,
    utc_now,
)
from .context import Service

logger = logging.getLogger(__name__)


class PaymentServices(Service):
    async def set_payout_block(
        self,
        *,
        order_id: UUID,
        blocked: bool,
        reason: str,
        admin_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            order = await uow.session.get(OrderModel, order_id, with_for_update=True)
            if order is None:
                raise NotFoundError("Order not found")
            if order.payout_status == "succeeded":
                raise ValidationError("Completed payout cannot be changed")
            if not blocked:
                dispute = await uow.session.scalar(
                    select(DisputeModel.id).where(
                        DisputeModel.order_id == order_id,
                        DisputeModel.status.in_(("open", "in_progress")),
                    ),
                )
                if dispute is not None:
                    raise ValidationError("Open dispute blocks payout")
                order.payout_status = "ready"
                order.payout_block_reason = None
            else:
                order.payout_status = "blocked"
                order.payout_block_reason = reason
            order.updated_at = utc_now()
            uow.session.add(
                AdminAuditLogModel(
                    admin_id=admin_id,
                    action="block_payout" if blocked else "allow_payout",
                    entity_type="order",
                    entity_id=order_id,
                    reason=reason,
                ),
            )
            await uow.commit()
            return order

    async def mark_manual_payout(
        self,
        *,
        order_id: UUID,
        reference: str,
        comment: str | None,
        admin_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            repository = SqlAlchemyPaymentRepository(uow.session)
            payout = await MarkManualPayoutUseCase(repository).execute(
                MarkManualPayoutCommand(
                    order_id=order_id,
                    reference=reference,
                    comment=comment,
                    admin_id=admin_id,
                ),
            )
            uow.session.add(
                AdminAuditLogModel(
                    admin_id=admin_id,
                    action="manual_payout_marked_paid",
                    entity_type="order",
                    entity_id=order_id,
                    reason=comment,
                    audit_metadata={
                        "amount": str(payout.amount),
                        "reference": reference,
                    },
                ),
            )
            await uow.commit()
            return payout

    async def retry_customer_payment(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            payment = await RetryCustomerPaymentUseCase(
                SqlAlchemyPaymentRepository(uow.session),
            ).execute(
                RetryCustomerPaymentCommand(
                    order_id=order_id,
                    customer_id=customer_id,
                ),
            )
            await uow.commit()
        try:
            await self.initialize_payment(payment.id)
        except Exception:
            logger.warning(
                "Payment retry initialization failed",
                extra={"payment_id": str(payment.id)},
                exc_info=True,
            )
        return await self.get_customer_payment_status(
            GetCustomerPaymentStatusCommand(
                order_id=order_id,
                customer_id=customer_id,
            ),
        )

    async def initialize_payment(self, payment_id: UUID) -> None:
        async with self._uow() as uow:
            repository = SqlAlchemyPaymentRepository(uow.session)
            data = await repository.get_initialization_data(payment_id)
        if data is None:
            raise NotFoundError("Payment not found")
        if data.payment.status != "created":
            return
        gateway = self._payment_gateway()
        description = f"Оплата заказа {data.payment.order_id} ({data.service_name})"
        try:
            result = await gateway.create_payment(
                PaymentGatewayInitCommand(
                    payment_id=data.payment.id,
                    order_id=data.payment.order_id,
                    idempotency_key=data.payment.idempotency_key,
                    amount=data.payment.amount,
                    description=description,
                    customer_phone=data.customer_phone,
                    customer_name=data.customer_name,
                ),
            )
        except Exception:
            async with self._uow() as uow:
                await SqlAlchemyPaymentRepository(
                    uow.session,
                ).mark_provider_initialization_failed(
                    payment_id=data.payment.id,
                    failure_code="provider_init_failed",
                )
                await uow.commit()
            raise
        async with self._uow() as uow:
            await SqlAlchemyPaymentRepository(uow.session).mark_provider_initialized(
                payment_id=data.payment.id,
                provider_payment_id=result.provider_payment_id,
                provider_deal_id=result.provider_deal_id,
                confirmation_url=result.confirmation_url,
            )
            await uow.commit()

    async def with_payment_prompt(self, result: Any) -> Any:
        async with self._uow() as uow:
            data = await SqlAlchemyPaymentRepository(
                uow.session,
            ).get_initialization_data(result.payment.payment_id)
        if data is None:
            return result
        return type(result)(
            order=result.order,
            match=result.match,
            payment=type(result.payment)(
                payment_id=data.payment.id,
                confirmation_url=data.payment.confirmation_url,
                expires_at=data.payment.expires_at,
                timezone=result.payment.timezone,
            ),
        )

    async def apply_payment_webhook(self, command: PaymentWebhookCommand) -> Any:
        async with self._uow() as uow:
            result = await ApplyPaymentWebhookUseCase(
                SqlAlchemyPaymentRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return result

    async def create_manual_refund(
        self,
        command: CreateManualRefundCommand,
    ) -> Any:
        async with self._uow() as uow:
            repository = SqlAlchemyPaymentRepository(uow.session)
            refund = await CreateManualRefundUseCase(repository).execute(command)
            data = await repository.get_initialization_data(refund.payment_id)
            if data is None or data.payment.provider_payment_id is None:
                raise ValidationError("Provider payment id is not available")
            uow.session.add(
                AdminAuditLogModel(
                    admin_id=command.admin_id,
                    action="manual_refund_created",
                    entity_type="refund",
                    entity_id=refund.id,
                    reason=command.reason,
                    audit_metadata={
                        "payment_id": str(command.payment_id),
                        "amount": str(refund.amount),
                    },
                ),
            )
            await uow.commit()
            provider_payment_id = data.payment.provider_payment_id
        if refund.status != "pending":
            return refund
        gateway = self._payment_gateway()
        try:
            result = await gateway.create_refund(
                PaymentGatewayRefundCommand(
                    refund_id=refund.id,
                    payment_id=refund.payment_id,
                    provider_payment_id=provider_payment_id,
                    idempotency_key=refund.idempotency_key,
                    amount=refund.amount,
                ),
            )
        except Exception:
            async with self._uow() as uow:
                repository = SqlAlchemyPaymentRepository(uow.session)
                await repository.mark_refund_failed(
                    refund_id=refund.id,
                )
                refund = await repository.get_refund(refund.id) or refund
                await uow.commit()
            raise
        async with self._uow() as uow:
            repository = SqlAlchemyPaymentRepository(uow.session)
            await repository.mark_refund_succeeded(
                refund_id=refund.id,
                provider_refund_id=result.provider_refund_id,
            )
            refund = await repository.get_refund(refund.id) or refund
            await uow.commit()
        return refund

    async def get_customer_payment_status(
        self,
        command: GetCustomerPaymentStatusCommand,
    ) -> Any:
        async with self._uow() as uow:
            return await GetCustomerPaymentStatusUseCase(
                SqlAlchemyPaymentRepository(uow.session),
            ).execute(command)

    async def retry_payment_operation(
        self,
        *,
        command: RetryPaymentOperationCommand,
        admin_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            result = await RetryPaymentOperationUseCase(
                SqlAlchemyPaymentRepository(uow.session),
                self._payment_gateway(),
            ).execute(command)
            uow.session.add(
                AdminAuditLogModel(
                    admin_id=admin_id,
                    action="retry_payment_operation",
                    entity_type="payment",
                    entity_id=command.payment_id,
                    reason=None,
                    audit_metadata={
                        "applied": result.applied if result is not None else False,
                        "status": result.status if result is not None else None,
                    },
                ),
            )
            await uow.commit()
            return result

from decimal import Decimal
from typing import Protocol
from uuid import UUID

from backend.modules.payments.application.dto import (
    PaymentGatewayInitCommand,
    PaymentGatewayInitResult,
    PaymentGatewayRefundCommand,
    PaymentGatewayRefundResult,
    PaymentGatewayStateCommand,
    PaymentGatewayStateResult,
    PaymentInitializationData,
    PaymentStatusDTO,
    PaymentWebhookCommand,
    PaymentWebhookResult,
    RefundDTO,
)


class PaymentGateway(Protocol):
    async def create_payment(
        self,
        command: PaymentGatewayInitCommand,
    ) -> PaymentGatewayInitResult:
        pass

    async def create_refund(
        self,
        command: PaymentGatewayRefundCommand,
    ) -> PaymentGatewayRefundResult:
        pass

    async def get_payment_state(
        self,
        command: PaymentGatewayStateCommand,
    ) -> PaymentGatewayStateResult:
        pass


class PaymentRepository(Protocol):
    async def get_initialization_data(
        self,
        payment_id: UUID,
    ) -> PaymentInitializationData | None:
        pass

    async def mark_provider_initialized(
        self,
        *,
        payment_id: UUID,
        provider_payment_id: str,
        provider_deal_id: str | None,
        confirmation_url: str,
    ) -> None:
        pass

    async def mark_provider_initialization_failed(
        self,
        *,
        payment_id: UUID,
        failure_code: str,
    ) -> None:
        pass

    async def apply_successful_webhook(
        self,
        command: PaymentWebhookCommand,
    ) -> PaymentWebhookResult | None:
        pass

    async def create_manual_refund(
        self,
        *,
        payment_id: UUID,
        amount: Decimal,
        reason: str,
        admin_id: UUID,
    ) -> RefundDTO:
        pass

    async def mark_refund_succeeded(
        self,
        *,
        refund_id: UUID,
        provider_refund_id: str,
    ) -> None:
        pass

    async def mark_refund_failed(self, *, refund_id: UUID) -> None:
        pass

    async def get_customer_payment_status(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> PaymentStatusDTO | None:
        pass

    async def mark_provider_status(
        self,
        *,
        payment_id: UUID,
        status: str,
        failure_code: str | None,
    ) -> None:
        pass

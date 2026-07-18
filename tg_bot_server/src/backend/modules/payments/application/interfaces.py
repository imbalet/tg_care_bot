from typing import Protocol
from uuid import UUID

from backend.modules.payments.application.dto import (
    PaymentGatewayInitCommand,
    PaymentGatewayInitResult,
    PaymentInitializationData,
)


class PaymentGateway(Protocol):
    async def create_payment(
        self,
        command: PaymentGatewayInitCommand,
    ) -> PaymentGatewayInitResult:
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

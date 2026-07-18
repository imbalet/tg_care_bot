from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class PaymentAttemptDTO:
    id: UUID
    order_id: UUID
    performer_id: UUID
    attempt_number: int
    provider: str
    provider_payment_id: str | None
    provider_deal_id: str | None
    idempotency_key: str
    amount: Decimal
    status: str
    confirmation_url: str | None
    expires_at: datetime


@dataclass(frozen=True)
class PaymentGatewayInitCommand:
    payment_id: UUID
    order_id: UUID
    idempotency_key: str
    amount: Decimal
    description: str
    customer_phone: str
    customer_name: str


@dataclass(frozen=True)
class PaymentGatewayInitResult:
    provider_payment_id: str
    provider_deal_id: str | None
    confirmation_url: str


@dataclass(frozen=True)
class PaymentInitializationData:
    payment: PaymentAttemptDTO
    customer_phone: str
    customer_name: str
    service_name: str


@dataclass(frozen=True)
class PaymentWebhookCommand:
    provider_payment_id: str
    status: str
    amount: Decimal
    paid_at: datetime
    raw_payload: dict[str, object]


@dataclass(frozen=True)
class PaymentWebhookResult:
    payment_id: UUID
    order_id: UUID
    status: str
    applied: bool
    unapplied_reason: str | None

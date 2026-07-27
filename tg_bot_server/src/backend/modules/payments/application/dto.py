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
    provider_status: str
    confirmation_url: str | None
    expires_at: datetime
    failure_code: str | None = None


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
    provider_order_id: UUID
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


@dataclass(frozen=True)
class RefundDTO:
    id: UUID
    order_id: UUID
    payment_id: UUID
    refund_type: str
    amount: Decimal
    status: str
    reason: str
    provider_refund_id: str | None
    idempotency_key: str


@dataclass(frozen=True)
class ManualPayoutDTO:
    order_id: UUID
    status: str
    amount: Decimal
    reference: str
    comment: str | None
    completed_at: datetime


@dataclass(frozen=True)
class PaymentGatewayRefundCommand:
    refund_id: UUID
    payment_id: UUID
    provider_payment_id: str
    idempotency_key: str
    amount: Decimal


@dataclass(frozen=True)
class PaymentGatewayRefundResult:
    provider_refund_id: str


@dataclass(frozen=True)
class PaymentGatewayStateCommand:
    provider_payment_id: str


@dataclass(frozen=True)
class PaymentGatewayStateResult:
    provider_payment_id: str
    status: str
    amount: Decimal
    paid_at: datetime


@dataclass(frozen=True)
class PaymentStatusDTO:
    order_id: UUID
    order_status: str
    payment_id: UUID | None
    payment_status: str | None
    confirmation_url: str | None
    expires_at: datetime | None
    failure_code: str | None = None
    attempts_used: int = 0
    max_attempts: int = 3
    retry_available: bool = False

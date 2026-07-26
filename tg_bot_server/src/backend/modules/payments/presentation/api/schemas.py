from typing import Any

from pydantic import BaseModel, Field


class TBankWebhookRequest(BaseModel):
    terminal_key: str = Field(validation_alias="TerminalKey")
    order_id: str = Field(validation_alias="OrderId")
    success: bool = Field(validation_alias="Success")
    status: str = Field(validation_alias="Status")
    payment_id: str = Field(validation_alias="PaymentId")
    amount: int = Field(validation_alias="Amount")
    token: str = Field(validation_alias="Token")
    raw: dict[str, Any] = Field(default_factory=dict)


class PaymentWebhookResponse(BaseModel):
    status: str


class PaymentStatusResponse(BaseModel):
    order_id: str
    order_status: str
    payment_id: str | None
    payment_status: str | None
    confirmation_url: str | None
    expires_at: str | None
    failure_code: str | None
    attempts_used: int
    max_attempts: int
    retry_available: bool

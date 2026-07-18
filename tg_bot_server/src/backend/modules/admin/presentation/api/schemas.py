from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1)


class AdminResponse(BaseModel):
    id: str
    email: str
    full_name: str
    status: str
    last_login_at: str | None


class LoginResponse(BaseModel):
    admin: AdminResponse
    csrf_token: str


class UpdateBusinessSettingRequest(BaseModel):
    value: Any


class BusinessSettingResponse(BaseModel):
    key: str
    value: Any
    value_type: str


class ManualRefundRequest(BaseModel):
    payment_id: UUID
    amount: str
    reason: str = Field(min_length=1, max_length=500)


class ManualRefundResponse(BaseModel):
    id: str
    order_id: str
    payment_id: str
    refund_type: str
    amount: str
    status: str
    reason: str
    provider_refund_id: str | None

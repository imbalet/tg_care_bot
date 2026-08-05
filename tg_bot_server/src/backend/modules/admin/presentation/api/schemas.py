from datetime import datetime, time
from decimal import Decimal
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


class AdminSessionResponse(BaseModel):
    admin: AdminResponse
    csrf_token: str


class AdminResourcePageResponse(BaseModel):
    items: list[dict[str, Any]]
    page: int
    page_size: int
    total: int


class AdminResourceDetailResponse(BaseModel):
    item: dict[str, Any]
    related: dict[str, list[dict[str, Any]]]


class AdminCommentRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=5000)


class AdminPerformerRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=200)
    comment: str = Field(min_length=1, max_length=5000)


class AdminPerformerServiceRequest(BaseModel):
    admin_max_objects: int = Field(ge=1)
    constraints: dict[str, Any] = Field(default_factory=dict)


class AdminAddPerformerServiceRequest(AdminPerformerServiceRequest):
    service_id: UUID
    comment: str = Field(min_length=1, max_length=5000)


class AdminManualPayoutRequest(BaseModel):
    reference: str = Field(min_length=1, max_length=200)
    comment: str | None = Field(default=None, max_length=5000)


class AdminPayoutDecisionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=5000)


class AdminRefundRequest(BaseModel):
    amount: str | None = None
    reason: str = Field(min_length=1, max_length=500)


class AdminSupportUpdateRequest(BaseModel):
    status: str = Field(min_length=1, max_length=100)
    comment: str | None = Field(default=None, max_length=10000)


class AdminInvitationRequest(BaseModel):
    telegram_id: int = Field(gt=0)
    expires_at: datetime | None = None


class AdminAssignPerformerRequest(BaseModel):
    performer_id: UUID
    comment: str = Field(min_length=1, max_length=5000)


class AdminOrderPerformerActionRequest(BaseModel):
    performer_id: UUID
    comment: str = Field(min_length=1, max_length=5000)


class AdminPerformerDecisionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    comment: str = Field(min_length=1, max_length=5000)


class AdminPerformerProfileRequest(BaseModel):
    phone: str = Field(min_length=1, max_length=100)
    contact_method: str = Field(min_length=1, max_length=30)
    comment: str = Field(min_length=1, max_length=5000)


class AdminPerformerServiceLimitsRequest(BaseModel):
    performer_max_objects: int = Field(ge=1)
    comment: str = Field(min_length=1, max_length=5000)


class AdminPerformerScheduleRequest(BaseModel):
    schedule_type: str
    work_days: list[int] | None = None
    work_start_time: time
    work_end_time: time


class AdminPerformerCalendarOverrideRequest(BaseModel):
    override_type: str
    starts_at: datetime
    ends_at: datetime
    comment: str | None = Field(default=None, max_length=500)


class AdminCatalogServiceRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price_type: str | None = None
    base_price: Decimal | None = Field(default=None, ge=0)
    location_policy: str | None = None
    photo_policy: str | None = None
    schedule_policy: str | None = None
    allows_multiday: bool | None = None
    min_duration_minutes: int | None = Field(default=None, ge=1)
    max_duration_minutes: int | None = Field(default=None, ge=1)
    duration_step_minutes: int | None = Field(default=None, ge=1)
    is_active: bool | None = None
    sort_order: int | None = None
    comment: str = Field(min_length=1, max_length=5000)


class AdminCatalogServiceOptionRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    value_type: str | None = None
    is_required: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    comment: str = Field(min_length=1, max_length=5000)


class AdminCatalogCityRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    timezone: str | None = None
    is_active: bool | None = None
    comment: str = Field(min_length=1, max_length=5000)


class AdminCatalogResourceUpdateRequest(BaseModel):
    changes: dict[str, Any]
    comment: str = Field(min_length=1, max_length=5000)


class AdminViolationRequest(BaseModel):
    account_type: str
    customer_id: UUID | None = None
    performer_id: UUID | None = None
    order_id: UUID | None = None
    case_type: str | None = None
    case_id: UUID | None = None
    violation_type: str = Field(min_length=1, max_length=200)
    action: str
    reason: str = Field(min_length=1, max_length=5000)


class AdminViolationResolveRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=5000)


class UpdateBusinessSettingRequest(BaseModel):
    value: Any


class BusinessSettingResponse(BaseModel):
    key: str
    value: Any
    value_type: str


class ManualRefundRequest(BaseModel):
    payment_id: UUID
    amount: str | None = None
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


class ManualPayoutRequest(BaseModel):
    order_id: UUID
    reference: str = Field(min_length=1, max_length=200)
    comment: str | None = Field(default=None, max_length=500)


class ManualPayoutResponse(BaseModel):
    order_id: str
    status: str
    amount: str
    reference: str
    comment: str | None
    completed_at: str


class PaymentRetryResponse(BaseModel):
    status: str
    applied: bool
    unapplied_reason: str | None


class AdminNotificationResponse(BaseModel):
    id: UUID
    type: str
    entity_type: str | None
    entity_id: UUID | None
    payload: dict[str, Any]
    status: str
    read_at: str | None
    created_at: str
    sent_at: str | None
    last_error: str | None
    attempts: int
    admin_retry_count: int


class AdminNotificationPageResponse(BaseModel):
    items: list[AdminNotificationResponse]
    page: int
    page_size: int
    total: int


class MarkAdminNotificationsReadRequest(BaseModel):
    ids: list[UUID] = Field(min_length=1)


class MarkAdminNotificationsReadResponse(BaseModel):
    marked: int

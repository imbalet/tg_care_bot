from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.application import utc_now
from backend.common.infrastructure.database import (
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UuidPrimaryKeyMixin,
)

ACTIVE_ORDER_STATUSES = (
    "searching",
    "waiting_payment",
    "confirmed",
    "in_progress",
    "waiting_report",
    "report_submitted",
)


class OrderModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id"),
        nullable=True,
    )
    service_id: Mapped[UUID] = mapped_column(ForeignKey("services.id"), nullable=False)
    service_code: Mapped[str] = mapped_column(Text, nullable=False)
    service_name: Mapped[str] = mapped_column(Text, nullable=False)
    schedule_policy: Mapped[str] = mapped_column(Text, nullable=False)
    photo_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    matching_mode: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="searching")
    selected_performer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("performers.id"),
        nullable=True,
    )
    selected_match_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("order_matches.id"),
        nullable=True,
    )
    active_payment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payments.id"),
        nullable=True,
    )
    address_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("addresses.id"),
        nullable=True,
    )
    location_source: Mapped[str] = mapped_column(Text, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    objects_count: Mapped[int] = mapped_column(nullable=False)
    customer_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_photo_consent: Mapped[bool | None] = mapped_column(nullable=True)
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    price_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    service_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    platform_fee_percent_at_order: Mapped[Decimal] = mapped_column(
        Numeric(8, 4),
        nullable=False,
    )
    platform_fee_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    performer_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payout_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    payout_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    provider_payout_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    payout_idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    payout_block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payout_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payout_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    provider_receipt_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    refund_policy_version_at_payment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    partial_refund_percent_at_payment: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4),
        nullable=True,
    )
    matching_deadline_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    payment_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    report_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    confirmation_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expired_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    requires_admin_attention: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )


class OrderMatchModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_matches"

    order_id: Mapped[UUID] = mapped_column(ForeignKey(OrderModel.id), nullable=False)
    performer_id: Mapped[UUID] = mapped_column(
        ForeignKey("performers.id"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    response_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    selected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    close_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class OrderCareObjectModel(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "order_care_objects"

    order_id: Mapped[UUID] = mapped_column(ForeignKey(OrderModel.id), nullable=False)
    care_object_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("care_objects.id"),
        nullable=True,
    )
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    display_name_at_order: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_at_order: Mapped[str | None] = mapped_column(Text, nullable=True)


class OrderOptionValueModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_option_values"

    order_id: Mapped[UUID] = mapped_column(ForeignKey(OrderModel.id), nullable=False)
    service_option_id: Mapped[UUID] = mapped_column(
        ForeignKey("service_options.id"),
        nullable=False,
    )
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)


class OrderStatusHistoryModel(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "order_status_history"

    order_id: Mapped[UUID] = mapped_column(ForeignKey(OrderModel.id), nullable=False)
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class OrderAddressSnapshotModel(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "order_address_snapshots"

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey(OrderModel.id),
        nullable=False,
        unique=True,
    )
    source_address_id: Mapped[UUID] = mapped_column(
        ForeignKey("addresses.id"),
        nullable=False,
    )
    city_name: Mapped[str] = mapped_column(Text, nullable=False)
    district_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    address_text: Mapped[str] = mapped_column(Text, nullable=False)
    fias_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    geocoding_provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    geocoding_quality: Mapped[str | None] = mapped_column(Text, nullable=True)
    entrance: Mapped[str | None] = mapped_column(Text, nullable=True)
    floor: Mapped[str | None] = mapped_column(Text, nullable=True)
    apartment: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class OrderReportModel(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "order_reports"

    order_id: Mapped[UUID] = mapped_column(ForeignKey(OrderModel.id), nullable=False)
    performer_id: Mapped[UUID] = mapped_column(
        ForeignKey("performers.id"),
        nullable=False,
    )
    completed_work: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    problem_flag: Mapped[bool] = mapped_column(nullable=False, default=False)
    problem_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

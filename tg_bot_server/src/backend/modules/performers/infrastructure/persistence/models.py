from datetime import datetime, time
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, SmallInteger, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.infrastructure.database import (
    Base,
    TimestampMixin,
    UuidPrimaryKeyMixin,
)


class PerformerModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "performers"

    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    telegram_username: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_method: Mapped[str] = mapped_column(Text, nullable=False)
    city_id: Mapped[UUID] = mapped_column(ForeignKey("cities.id"), nullable=False)
    about_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="profile_pending",
    )
    is_accepting_orders: Mapped[bool] = mapped_column(nullable=False, default=False)
    current_address_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("addresses.id"),
        nullable=True,
    )
    payment_recipient_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        unique=True,
    )
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    anonymized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class PerformerInvitationModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "performer_invitations"

    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_by_admin_id: Mapped[UUID] = mapped_column(
        ForeignKey("admins.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    accepted_performer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(PerformerModel.id),
        nullable=True,
    )


class PerformerServiceModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "performer_services"

    performer_id: Mapped[UUID] = mapped_column(
        ForeignKey(PerformerModel.id),
        nullable=False,
    )
    service_id: Mapped[UUID] = mapped_column(ForeignKey("services.id"), nullable=False)
    is_approved: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    admin_max_objects: Mapped[int] = mapped_column(nullable=False)
    performer_max_objects: Mapped[int] = mapped_column(nullable=False)
    constraints: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    approved_by_admin_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("admins.id"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class PerformerScheduleModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "performer_schedules"

    performer_id: Mapped[UUID] = mapped_column(
        ForeignKey(PerformerModel.id),
        nullable=False,
    )
    schedule_type: Mapped[str] = mapped_column(Text, nullable=False)
    work_days: Mapped[list[int] | None] = mapped_column(
        ARRAY(SmallInteger),
        nullable=True,
    )
    work_start_time: Mapped[time] = mapped_column(nullable=False)
    work_end_time: Mapped[time] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class PerformerCalendarOverrideModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "performer_calendar_overrides"

    performer_id: Mapped[UUID] = mapped_column(
        ForeignKey(PerformerModel.id),
        nullable=False,
    )
    override_type: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

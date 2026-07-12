from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.infrastructure.database import (
    Base,
    TimestampMixin,
    UuidPrimaryKeyMixin,
)


class PerformerModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "performers"

    telegram_id: Mapped[int] = mapped_column(nullable=False, unique=True)
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

    telegram_id: Mapped[int] = mapped_column(nullable=False)
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
        ForeignKey("performers.id"),
        nullable=True,
    )


__all__ = ["PerformerInvitationModel", "PerformerModel"]

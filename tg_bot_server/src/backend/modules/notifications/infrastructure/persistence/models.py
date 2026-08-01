from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.infrastructure.database import (
    Base,
    TimestampMixin,
    UuidPrimaryKeyMixin,
)


class NotificationModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    recipient_type: Mapped[str] = mapped_column(Text, nullable=False)
    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id"),
        nullable=True,
    )
    performer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("performers.id"),
        nullable=True,
    )
    admin_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("admins.id"), nullable=True
    )
    recipient_telegram_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False, default="telegram")
    type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_id: Mapped[UUID | None] = mapped_column(nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    deduplication_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    admin_retry_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    delete_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

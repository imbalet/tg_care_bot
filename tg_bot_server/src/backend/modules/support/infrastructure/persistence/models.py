from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.infrastructure.database import (
    Base,
    TimestampMixin,
    UuidPrimaryKeyMixin,
)


class SupportRequestModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "support_requests"

    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True
    )
    performer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("performers.id"), nullable=True
    )
    order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("orders.id"), nullable=True
    )
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    admin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class ComplaintModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "complaints"

    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True
    )
    performer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("performers.id"), nullable=True
    )
    order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("orders.id"), nullable=True
    )
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    admin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class DisputeModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "disputes"

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id"), nullable=False
    )
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    admin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class AccountDeletionRequestModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "account_deletion_requests"

    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True
    )
    performer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("performers.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    blockers: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    admin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

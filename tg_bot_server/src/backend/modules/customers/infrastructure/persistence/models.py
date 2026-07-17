from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.application import utc_now
from backend.common.infrastructure.database import (
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UuidPrimaryKeyMixin,
)


class CustomerModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    telegram_id: Mapped[int] = mapped_column(nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    telegram_username: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_method: Mapped[str] = mapped_column(Text, nullable=False)
    city_id: Mapped[UUID] = mapped_column(ForeignKey("cities.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    anonymized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class LegalAcceptanceModel(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "legal_acceptances"

    account_type: Mapped[str] = mapped_column(Text, nullable=False)
    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id"),
        nullable=True,
    )
    performer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("performers.id"),
        nullable=True,
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("legal_documents.id"),
        nullable=False,
    )
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

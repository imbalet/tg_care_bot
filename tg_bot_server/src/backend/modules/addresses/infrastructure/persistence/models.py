from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.infrastructure.database import (
    Base,
    TimestampMixin,
    UuidPrimaryKeyMixin,
)


class AddressModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "addresses"

    owner_type: Mapped[str] = mapped_column(Text, nullable=False)
    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id"),
        nullable=True,
    )
    performer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("performers.id"),
        nullable=True,
    )
    city_id: Mapped[UUID] = mapped_column(ForeignKey("cities.id"), nullable=False)
    district_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("districts.id"),
        nullable=True,
    )
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
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    anonymized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


__all__ = ["AddressModel"]

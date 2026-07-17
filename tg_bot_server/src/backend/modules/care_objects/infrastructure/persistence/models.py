from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.infrastructure.database import (
    Base,
    TimestampMixin,
    UuidPrimaryKeyMixin,
)


class CareObjectModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "care_objects"

    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"))
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    age_group: Mapped[str] = mapped_column(Text, nullable=False)
    species: Mapped[str | None] = mapped_column(Text, nullable=True)
    breed: Mapped[str | None] = mapped_column(Text, nullable=True)
    pet_size: Mapped[str | None] = mapped_column(Text, nullable=True)
    mobility_assistance_required: Mapped[bool | None] = mapped_column(nullable=True)
    routine_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    behavior_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    anonymized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.application import new_uuid, utc_now


class UuidPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


__all__ = ["CreatedAtMixin", "TimestampMixin", "UuidPrimaryKeyMixin"]

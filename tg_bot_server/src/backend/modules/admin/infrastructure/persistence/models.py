from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.infrastructure.database import (
    Base,
    TimestampMixin,
    UuidPrimaryKeyMixin,
)


class AdminModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "admins"

    email: Mapped[str] = mapped_column(String(length=320), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(length=200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(length=500), nullable=False)
    status: Mapped[str] = mapped_column(
        String(length=32),
        nullable=False,
        default="active",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


__all__ = ["AdminModel"]

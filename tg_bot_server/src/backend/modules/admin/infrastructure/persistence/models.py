from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.infrastructure.database import Base


class AdminModel(Base):
    __tablename__ = "admins"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(length=320), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(length=200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(length=500), nullable=False)
    status: Mapped[str] = mapped_column(String(length=32), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


__all__ = ["AdminModel"]

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.application import utc_now
from backend.common.infrastructure.database import (
    Base,
    TimestampMixin,
    UuidPrimaryKeyMixin,
)


class AdminViolationModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "admin_violations"

    account_type: Mapped[str] = mapped_column(Text, nullable=False)
    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True
    )
    performer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("performers.id"), nullable=True
    )
    order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("orders.id"), nullable=True
    )
    case_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_id: Mapped[UUID | None] = mapped_column(nullable=True)
    violation_type: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    created_by_admin_id: Mapped[UUID] = mapped_column(
        ForeignKey("admins.id"), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def resolve(self) -> None:
        self.status = "resolved"
        self.resolved_at = utc_now()

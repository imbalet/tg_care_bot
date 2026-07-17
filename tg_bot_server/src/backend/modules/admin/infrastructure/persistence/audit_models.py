from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.infrastructure.database import (
    Base,
    CreatedAtMixin,
    UuidPrimaryKeyMixin,
)


class AdminAuditLogModel(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "admin_audit_logs"

    admin_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("admins.id"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

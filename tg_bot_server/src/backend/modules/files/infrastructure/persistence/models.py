from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.infrastructure.database import (
    Base,
    CreatedAtMixin,
    UuidPrimaryKeyMixin,
)


class FileModel(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "files"

    telegram_file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    bucket: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="uploaded")
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class FileLinkModel(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "file_links"

    file_id: Mapped[UUID] = mapped_column(ForeignKey("files.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[UUID] = mapped_column(nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)


__all__ = ["FileLinkModel", "FileModel"]

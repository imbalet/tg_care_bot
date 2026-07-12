from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.infrastructure.database import (
    Base,
    CreatedAtMixin,
    UuidPrimaryKeyMixin,
)


class SystemCheckRecordModel(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "system_check_records"

    name: Mapped[str] = mapped_column(String(length=100), nullable=False)


__all__ = ["SystemCheckRecordModel"]

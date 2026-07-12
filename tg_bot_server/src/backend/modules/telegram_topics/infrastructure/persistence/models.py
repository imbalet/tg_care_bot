from uuid import UUID

from sqlalchemy import BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.infrastructure.database import (
    Base,
    TimestampMixin,
    UuidPrimaryKeyMixin,
)


class TelegramTopicModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "telegram_topics"

    account_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    topic_kind: Mapped[str] = mapped_column(Text, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="fallback")


__all__ = ["TelegramTopicModel"]

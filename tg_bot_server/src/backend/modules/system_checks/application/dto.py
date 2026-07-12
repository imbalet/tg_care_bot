from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class SystemCheckRecordDTO:
    id: UUID
    name: str
    created_at: datetime


__all__ = ["SystemCheckRecordDTO"]

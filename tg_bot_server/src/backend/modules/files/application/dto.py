from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class FileDTO:
    id: UUID
    telegram_file_id: str | None
    bucket: str
    storage_key: str | None
    original_name: str | None
    mime_type: str
    size_bytes: int | None
    checksum: str | None
    status: str
    created_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True)
class FileLinkDTO:
    id: UUID
    file_id: UUID
    entity_type: str
    entity_id: UUID
    purpose: str
    sort_order: int
    created_at: datetime


@dataclass(frozen=True)
class CreateFileCommand:
    telegram_file_id: str | None
    bucket: str
    storage_key: str
    original_name: str | None
    mime_type: str
    size_bytes: int
    checksum: str
    status: str = "uploaded"


@dataclass(frozen=True)
class CreateFileLinkCommand:
    file_id: UUID
    entity_type: str
    entity_id: UUID
    purpose: str
    sort_order: int = 0

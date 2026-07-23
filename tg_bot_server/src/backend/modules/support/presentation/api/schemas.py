from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CreateSupportRequest(BaseModel):
    order_id: UUID | None = None
    type: str
    text: str = Field(min_length=1, max_length=10000)
    file_ids: list[UUID] = Field(default_factory=list, max_length=10)


class CreateComplaintRequest(BaseModel):
    order_id: UUID | None = None
    category: str
    text: str = Field(min_length=1, max_length=10000)
    file_ids: list[UUID] = Field(default_factory=list, max_length=10)


class UpdateSupportRecordRequest(BaseModel):
    status: str
    admin_comment: str | None = Field(default=None, max_length=10000)


class SupportFileResponse(BaseModel):
    id: UUID
    name: str | None
    mime_type: str
    size_bytes: int | None
    url: str | None


class SupportRecordResponse(BaseModel):
    id: UUID
    kind: str
    customer_id: UUID | None
    performer_id: UUID | None
    order_id: UUID | None
    direction: str | None
    type: str | None
    category: str | None
    text: str | None
    status: str
    blockers: list[dict[str, Any]]
    admin_comment: str | None
    created_at: str
    updated_at: str
    resolved_at: str | None
    files: list[SupportFileResponse] = Field(default_factory=list)


class SupportRecordPageResponse(BaseModel):
    items: list[SupportRecordResponse]
    page: int
    page_size: int
    total: int


class AccountDeletionPreflightResponse(BaseModel):
    can_delete: bool
    blockers: list[dict[str, Any]]

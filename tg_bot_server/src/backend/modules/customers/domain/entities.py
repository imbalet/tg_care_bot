from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ContactMethod(StrEnum):
    TELEGRAM = "telegram"
    PHONE = "phone"
    BOTH = "both"


class CustomerStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    DELETION_PENDING = "deletion_pending"
    ANONYMIZED = "anonymized"


@dataclass
class Customer:
    id: UUID
    telegram_id: int
    full_name: str
    phone: str
    telegram_username: str | None
    contact_method: ContactMethod
    city_id: UUID
    status: CustomerStatus
    blocked_reason: str | None
    deleted_at: datetime | None
    anonymized_at: datetime | None
    created_at: datetime
    updated_at: datetime


__all__ = ["ContactMethod", "Customer", "CustomerStatus"]

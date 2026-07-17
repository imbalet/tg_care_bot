from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class AdminStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"


@dataclass
class Admin:
    id: UUID
    email: str
    full_name: str
    password_hash: str
    status: AdminStatus
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def ensure_active(self) -> None:
        from backend.common.domain import AuthorizationError

        if self.status != AdminStatus.ACTIVE:
            raise AuthorizationError("Admin is blocked")

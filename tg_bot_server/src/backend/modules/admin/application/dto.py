from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class AdminDTO:
    id: UUID
    email: str
    full_name: str
    status: str
    last_login_at: datetime | None


@dataclass(frozen=True)
class AdminSessionDTO:
    admin: AdminDTO
    session_id: str
    csrf_token: str

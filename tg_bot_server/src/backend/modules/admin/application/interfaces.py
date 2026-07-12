from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from backend.modules.admin.domain import Admin


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str:
        pass

    def verify(self, password_hash: str, password: str) -> bool:
        pass


@dataclass(frozen=True)
class AdminSession:
    session_id: str
    admin_id: UUID
    csrf_token: str


class AdminSessionStore(Protocol):
    async def create(self, admin_id: UUID) -> AdminSession:
        pass

    async def get(self, session_id: str) -> AdminSession | None:
        pass

    async def delete(self, session_id: str) -> None:
        pass


class AdminRepository(Protocol):
    async def get_by_id(self, admin_id: UUID) -> Admin | None:
        pass

    async def get_by_email(self, email: str) -> Admin | None:
        pass

    async def add(self, admin: Admin) -> None:
        pass

    async def update_last_login(self, admin: Admin) -> None:
        pass


__all__ = [
    "AdminRepository",
    "AdminSession",
    "AdminSessionStore",
    "PasswordHasher",
]

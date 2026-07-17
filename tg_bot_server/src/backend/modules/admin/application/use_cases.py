from dataclasses import dataclass

from backend.common.application import Clock, SystemClock, new_uuid
from backend.common.domain import AuthenticationError, ConflictError
from backend.modules.admin.application.dto import AdminDTO, AdminSessionDTO
from backend.modules.admin.application.interfaces import (
    AdminRepository,
    AdminSessionStore,
    PasswordHasher,
)
from backend.modules.admin.domain import Admin, AdminStatus


def _to_dto(admin: Admin) -> AdminDTO:
    return AdminDTO(
        id=admin.id,
        email=admin.email,
        full_name=admin.full_name,
        status=admin.status.value,
        last_login_at=admin.last_login_at,
    )


@dataclass(frozen=True)
class LoginAdminCommand:
    email: str
    password: str


class LoginAdminUseCase:
    def __init__(
        self,
        repository: AdminRepository,
        password_hasher: PasswordHasher,
        session_store: AdminSessionStore,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._session_store = session_store

    async def execute(self, command: LoginAdminCommand) -> AdminSessionDTO:
        admin = await self._repository.get_by_email(command.email.lower())
        if admin is None:
            raise AuthenticationError("Invalid email or password")
        if not self._password_hasher.verify(admin.password_hash, command.password):
            raise AuthenticationError("Invalid email or password")
        admin.ensure_active()
        await self._repository.update_last_login(admin)
        session = await self._session_store.create(admin.id)
        return AdminSessionDTO(
            admin=_to_dto(admin),
            session_id=session.session_id,
            csrf_token=session.csrf_token,
        )


class GetCurrentAdminUseCase:
    def __init__(
        self,
        repository: AdminRepository,
        session_store: AdminSessionStore,
    ) -> None:
        self._repository = repository
        self._session_store = session_store

    async def execute(self, session_id: str) -> tuple[AdminDTO, str]:
        session = await self._session_store.get(session_id)
        if session is None:
            raise AuthenticationError("Admin session is invalid")
        admin = await self._repository.get_by_id(session.admin_id)
        if admin is None:
            raise AuthenticationError("Admin session is invalid")
        admin.ensure_active()
        return _to_dto(admin), session.csrf_token


class LogoutAdminUseCase:
    def __init__(self, session_store: AdminSessionStore) -> None:
        self._session_store = session_store

    async def execute(self, session_id: str) -> None:
        await self._session_store.delete(session_id)


@dataclass(frozen=True)
class BootstrapAdminCommand:
    email: str
    full_name: str
    password: str


class BootstrapAdminUseCase:
    def __init__(
        self,
        repository: AdminRepository,
        password_hasher: PasswordHasher,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._clock = clock or SystemClock()

    async def execute(self, command: BootstrapAdminCommand) -> AdminDTO:
        email = command.email.lower()
        existing = await self._repository.get_by_email(email)
        if existing is not None:
            raise ConflictError("Admin already exists")
        now = self._clock.now()
        admin = Admin(
            id=new_uuid(),
            email=email,
            full_name=command.full_name,
            password_hash=self._password_hasher.hash(command.password),
            status=AdminStatus.ACTIVE,
            last_login_at=None,
            created_at=now,
            updated_at=now,
        )
        await self._repository.add(admin)
        return _to_dto(admin)

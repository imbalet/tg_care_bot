from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.bootstrap.api import create_app
from backend.bootstrap.settings import get_settings
from backend.modules.admin.domain import Admin, AdminStatus
from backend.modules.admin.infrastructure import Argon2PasswordHasher
from backend.modules.admin.presentation.api import routes


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int) -> None:
        self.values[key] = value

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


class FakeSession:
    committed = False

    async def commit(self) -> None:
        self.committed = True


class FakeSessionFactory:
    def __init__(self) -> None:
        self.session = FakeSession()

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(self, *args: object) -> None:
        return None

    def __call__(self) -> FakeSessionFactory:
        return self


class FakeAdminRepository:
    admin: Admin | None = None

    def __init__(self, _session: FakeSession) -> None:
        pass

    async def get_by_id(self, _admin_id: UUID) -> Admin | None:
        return self.admin

    async def get_by_email(self, email: str) -> Admin | None:
        if self.admin is not None and self.admin.email == email:
            return self.admin
        return None

    async def add(self, admin: Admin) -> None:
        self.admin = admin

    async def update_last_login(self, admin: Admin) -> None:
        admin.last_login_at = datetime.now(UTC)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    get_settings.cache_clear()
    monkeypatch.setattr(routes, "SqlAlchemyAdminRepository", FakeAdminRepository)
    app = create_app()
    with TestClient(app) as test_client:
        settings = SimpleNamespace(
            admin_session_ttl_seconds=60,
            environment="local",
        )
        app.state.container = SimpleNamespace(
            redis=FakeRedis(),
            settings=settings,
            session_factory=FakeSessionFactory(),
        )
        yield test_client
    get_settings.cache_clear()


def make_admin(status: AdminStatus = AdminStatus.ACTIVE) -> Admin:
    now = datetime.now(UTC)
    hasher = Argon2PasswordHasher()
    return Admin(
        id=uuid4(),
        email="admin@example.com",
        full_name="Admin User",
        password_hash=hasher.hash("secret-password"),
        status=status,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def login(client: TestClient) -> tuple[str, str]:
    response = client.post(
        "/admin/login",
        json={"email": "admin@example.com", "password": "secret-password"},
    )
    assert response.status_code == 200
    session_cookie = response.cookies.get(routes.ADMIN_SESSION_COOKIE)
    assert session_cookie is not None
    return session_cookie, response.json()["csrf_token"]


def test_login_sets_admin_session_cookie(client: TestClient) -> None:
    FakeAdminRepository.admin = make_admin()

    response = client.post(
        "/admin/login",
        json={"email": "admin@example.com", "password": "secret-password"},
    )

    assert response.status_code == 200
    assert response.cookies.get(routes.ADMIN_SESSION_COOKIE)
    assert response.json()["admin"]["email"] == "admin@example.com"
    assert response.json()["csrf_token"]


def test_login_rejects_blocked_admin(client: TestClient) -> None:
    FakeAdminRepository.admin = make_admin(AdminStatus.BLOCKED)

    response = client.post(
        "/admin/login",
        json={"email": "admin@example.com", "password": "secret-password"},
    )

    assert response.status_code == 403


def test_logout_requires_csrf(client: TestClient) -> None:
    FakeAdminRepository.admin = make_admin()
    session_cookie, _csrf_token = login(client)

    response = client.post(
        "/admin/logout",
        cookies={routes.ADMIN_SESSION_COOKIE: session_cookie},
    )

    assert response.status_code == 403


def test_logout_deletes_session_with_valid_csrf(client: TestClient) -> None:
    FakeAdminRepository.admin = make_admin()
    session_cookie, csrf_token = login(client)

    response = client.post(
        "/admin/logout",
        headers={routes.CSRF_HEADER: csrf_token},
        cookies={routes.ADMIN_SESSION_COOKIE: session_cookie},
    )

    assert response.status_code == 204

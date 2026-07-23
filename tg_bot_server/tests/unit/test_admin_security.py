from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from backend.common.domain import AuthenticationError
from backend.modules.admin.application.use_cases import (
    LoginAdminCommand,
    LoginAdminUseCase,
)
from backend.modules.admin.domain import Admin, AdminStatus


def _admin(status: AdminStatus = AdminStatus.ACTIVE) -> Admin:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    stored_hash = "stored-hash"
    return Admin(
        id=uuid4(),
        email="admin@example.com",
        full_name="Admin",
        password_hash=stored_hash,
        status=status,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.unit
async def test_admin_login_normalizes_email_and_creates_session() -> None:
    repository = AsyncMock()
    hasher = Mock()
    sessions = AsyncMock()
    admin = _admin()
    repository.get_by_email.return_value = admin
    hasher.verify.return_value = True
    sessions.create.return_value = type(
        "Session",
        (),
        {"session_id": "session", "csrf_token": "csrf"},
    )()

    result = await LoginAdminUseCase(repository, hasher, sessions).execute(
        LoginAdminCommand("ADMIN@EXAMPLE.COM", "password"),
    )

    repository.get_by_email.assert_awaited_once_with("admin@example.com")
    sessions.create.assert_awaited_once_with(admin.id)
    assert result.session_id == "session"


@pytest.mark.unit
async def test_admin_login_rejects_unknown_admin_without_password_probe() -> None:
    repository = AsyncMock()
    hasher = Mock()
    sessions = AsyncMock()
    repository.get_by_email.return_value = None

    with pytest.raises(AuthenticationError):
        await LoginAdminUseCase(repository, hasher, sessions).execute(
            LoginAdminCommand("missing@example.com", "password"),
        )

    hasher.verify.assert_not_called()
    sessions.create.assert_not_awaited()

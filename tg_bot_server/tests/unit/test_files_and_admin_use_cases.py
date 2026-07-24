from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from backend.common.domain import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    ValidationError,
)
from backend.modules.admin.application.use_cases import (
    BootstrapAdminCommand,
    BootstrapAdminUseCase,
    GetCurrentAdminUseCase,
    LoginAdminCommand,
    LoginAdminUseCase,
    LogoutAdminUseCase,
)
from backend.modules.admin.domain import Admin, AdminStatus
from backend.modules.files.application.avatar import validate_avatar_file
from backend.modules.files.application.upload import (
    UploadActorFileCommand,
    UploadActorFileUseCase,
)
from tests.support.fakes import FakeClock, FakeObjectStorage


def _admin(status: AdminStatus) -> Admin:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return Admin(
        id=uuid4(),
        email="admin@example.com",
        full_name="Admin",
        password_hash=str(uuid4()),
        status=status,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.unit
async def test_upload_actor_file_persists_storage_and_owner_link() -> None:
    customers = AsyncMock()
    performers = AsyncMock()
    files = AsyncMock()
    storage = FakeObjectStorage()
    customer_id = uuid4()
    file_id = uuid4()
    customers.get_by_telegram_id.return_value = SimpleNamespace(id=customer_id)
    files.add_file.return_value = SimpleNamespace(id=file_id)

    result = await UploadActorFileUseCase(
        customers,
        performers,
        files,
        storage,
    ).execute(
        UploadActorFileCommand(
            actor_type="customer",
            telegram_id=1,
            content=b"%PDF-1.7 content",
            content_type="application/pdf",
            original_name="document.pdf",
        ),
    )

    assert result.id == file_id
    assert len(storage.objects) == 1
    files.add_link.assert_awaited_once()
    assert files.add_link.call_args.args[0].entity_id == customer_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "command",
    [
        UploadActorFileCommand("customer", 1, b"", "image/png", None),
        UploadActorFileCommand("customer", 1, b"not-png", "image/png", None),
        UploadActorFileCommand("customer", 1, b"data", "text/plain", None),
    ],
)
async def test_upload_actor_file_rejects_empty_type_and_signature(
    command: UploadActorFileCommand,
) -> None:
    customers = AsyncMock()
    performers = AsyncMock()
    files = AsyncMock()
    storage = FakeObjectStorage()

    with pytest.raises(ValidationError):
        await UploadActorFileUseCase(
            customers,
            performers,
            files,
            storage,
        ).execute(command)

    storage.objects.clear()
    files.add_file.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("content", "content_type"),
    [(b"", "image/png"), (b"RIFF0000WEBP", "image/png")],
)
def test_avatar_validation_rejects_empty_or_mismatched_signature(
    content: bytes,
    content_type: str,
) -> None:
    with pytest.raises(ValidationError):
        validate_avatar_file(content=content, content_type=content_type)


@pytest.mark.unit
async def test_admin_bootstrap_normalizes_email_and_rejects_duplicate() -> None:
    repository = AsyncMock()
    hasher = Mock()
    hasher.hash.return_value = "hash"
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    repository.get_by_email.return_value = None

    result = await BootstrapAdminUseCase(repository, hasher, clock).execute(
        BootstrapAdminCommand("ADMIN@EXAMPLE.COM", "Admin", "password"),
    )
    assert result.email == "admin@example.com"
    repository.add.assert_awaited_once()

    repository.get_by_email.return_value = SimpleNamespace(id=uuid4())
    with pytest.raises(ConflictError):
        await BootstrapAdminUseCase(repository, hasher, clock).execute(
            BootstrapAdminCommand("admin@example.com", "Admin", "password"),
        )


@pytest.mark.unit
async def test_admin_session_requires_active_admin_and_logout_deletes_session() -> None:
    repository = AsyncMock()
    sessions = AsyncMock()
    csrf_token = str(uuid4())
    session = SimpleNamespace(admin_id=uuid4(), csrf_token=csrf_token)
    sessions.get.return_value = session
    admin = _admin(AdminStatus.ACTIVE)
    admin.id = session.admin_id
    repository.get_by_id.return_value = admin

    result = await GetCurrentAdminUseCase(repository, sessions).execute("sid")
    assert result[1] == csrf_token
    await LogoutAdminUseCase(sessions).execute("sid")
    sessions.delete.assert_awaited_once_with("sid")

    sessions.get.return_value = None
    with pytest.raises(AuthenticationError):
        await GetCurrentAdminUseCase(repository, sessions).execute("missing")


@pytest.mark.unit
async def test_admin_login_rejects_blocked_admin() -> None:
    repository = AsyncMock()
    hasher = Mock()
    sessions = AsyncMock()
    repository.get_by_email.return_value = _admin(AdminStatus.BLOCKED)
    hasher.verify.return_value = True

    with pytest.raises(AuthorizationError):
        await LoginAdminUseCase(repository, hasher, sessions).execute(
            LoginAdminCommand("admin@example.com", "password"),
        )
    sessions.create.assert_not_awaited()

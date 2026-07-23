import pytest

from backend.bootstrap.settings import get_settings
from backend.common.domain import AuthenticationError
from backend.common.presentation.auth import require_service_key


@pytest.mark.api
async def test_service_key_accepts_only_configured_value() -> None:
    settings = get_settings()

    await require_service_key(settings.service_key)

    with pytest.raises(AuthenticationError):
        await require_service_key("wrong-service-key")


@pytest.mark.api
async def test_service_key_rejects_missing_value() -> None:
    with pytest.raises(AuthenticationError):
        await require_service_key(None)

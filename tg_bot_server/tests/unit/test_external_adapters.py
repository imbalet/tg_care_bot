from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from backend.common.domain import ValidationError
from backend.modules.files.application.avatar import (
    UploadPerformerAvatarCommand,
    UploadPerformerAvatarUseCase,
    validate_avatar_file,
)
from backend.modules.files.application.dto import FileDTO
from backend.modules.geo.infrastructure.dadata import DaDataGeocoder
from tests.support.fakes import FakeObjectStorage


class _Response:
    status_code = 200

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def json(self) -> dict[str, object]:
        return self.payload


class _Client:
    response: _Response

    def __init__(self, **_: object) -> None:
        pass

    async def __aenter__(self) -> _Client:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(self, *_: object, **__: object) -> _Response:
        return self.response


@pytest.mark.unit
def test_avatar_validation_checks_signature_and_mime() -> None:
    assert validate_avatar_file(
        content=b"\x89PNG\r\n\x1a\ncontent",
        content_type="image/png",
    ) == ("image/png", ".png")
    with pytest.raises(ValidationError, match="MIME"):
        validate_avatar_file(
            content=b"\x89PNG\r\n\x1a\ncontent",
            content_type="image/jpeg",
        )
    with pytest.raises(ValidationError, match="not allowed"):
        validate_avatar_file(content=b"text", content_type="text/plain")


@pytest.mark.unit
async def test_avatar_upload_stores_file_and_replaces_previous_link() -> None:
    performer_repository = AsyncMock()
    file_repository = AsyncMock()
    storage = FakeObjectStorage()
    performer_id = uuid4()
    file_id = uuid4()
    performer_repository.get_performer_by_telegram_id.return_value = SimpleNamespace(
        id=performer_id,
    )
    file_repository.add_file.return_value = FileDTO(
        id=file_id,
        telegram_file_id="telegram-file",
        bucket="test-bucket",
        storage_key="avatars/file.png",
        original_name="avatar.png",
        mime_type="image/png",
        size_bytes=15,
        checksum="checksum",
        status="uploaded",
        created_at=datetime.now(UTC),
        deleted_at=None,
    )

    result = await UploadPerformerAvatarUseCase(
        performer_repository,
        file_repository,
        storage,
    ).execute(
        UploadPerformerAvatarCommand(
            telegram_id=1,
            content=b"\x89PNG\r\n\x1a\ncontent",
            content_type="image/png",
            original_name="avatar.png",
            telegram_file_id="telegram-file",
        ),
    )

    assert result.id == file_id
    assert len(storage.objects) == 1
    file_repository.replace_avatar_link.assert_awaited_once_with(
        file_id=file_id,
        entity_type="performer",
        entity_id=performer_id,
    )


@pytest.mark.unit
async def test_dadata_adapter_maps_suggestions_and_normalized_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    client.response = _Response(
        {
            "suggestions": [
                {
                    "value": "Moscow, Main street, 1",
                    "unrestricted_value": "Moscow, Main street, 1",
                    "data": {
                        "fias_id": "fias",
                        "geo_lat": "55.75",
                        "geo_lon": "37.61",
                        "qc_geo": "0",
                    },
                },
                {"value": 42, "unrestricted_value": "invalid"},
            ],
        },
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: client)
    geocoder_secret = str(uuid4())
    geocoder = DaDataGeocoder(
        api_key="api-key",
        secret_key=geocoder_secret,
        base_url="https://dadata.test",
        timeout_seconds=1,
        retry_count=0,
    )

    suggestions = await geocoder.suggest(query="Main", city="Moscow")
    normalized = await geocoder.normalize(
        unrestricted_value="Moscow, Main street, 1",
    )
    assert len(suggestions) == 1
    assert normalized.provider == "dadata"
    assert str(normalized.latitude) == "55.75"


@pytest.mark.unit
async def test_dadata_adapter_rejects_missing_key_and_empty_normalization() -> None:
    geocoder = DaDataGeocoder(
        api_key="",
        secret_key="",
        base_url="https://dadata.test",
        timeout_seconds=1,
        retry_count=0,
    )
    with pytest.raises(ValidationError, match="API key"):
        await geocoder.suggest(query="Main")


@pytest.mark.unit
async def test_dadata_adapter_rejects_ambiguous_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    client.response = _Response(
        {
            "suggestions": [
                {
                    "value": "Moscow, Main street, 1",
                    "unrestricted_value": "Moscow, Main street, 1",
                },
                {
                    "value": "Moscow, Main street, 2",
                    "unrestricted_value": "Moscow, Main street, 2",
                },
            ],
        },
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: client)
    geocoder = DaDataGeocoder(
        api_key="api-key",
        secret_key="",
        base_url="https://dadata.test",
        timeout_seconds=1,
        retry_count=0,
    )

    with pytest.raises(ValidationError, match="ambiguous"):
        await geocoder.normalize(unrestricted_value="Main street")

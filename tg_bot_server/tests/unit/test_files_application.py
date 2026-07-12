import pytest

from backend.common.domain import ValidationError
from backend.modules.files.application import validate_avatar_file


def test_validate_avatar_accepts_png_signature() -> None:
    mime_type, extension = validate_avatar_file(
        content=b"\x89PNG\r\n\x1a\npayload",
        content_type="image/png",
    )

    assert mime_type == "image/png"
    assert extension == ".png"


def test_validate_avatar_rejects_mime_mismatch() -> None:
    with pytest.raises(ValidationError):
        validate_avatar_file(
            content=b"\x89PNG\r\n\x1a\npayload",
            content_type="image/jpeg",
        )


def test_validate_avatar_rejects_oversize() -> None:
    with pytest.raises(ValidationError):
        validate_avatar_file(content=b"x" * (5 * 1024 * 1024 + 1), content_type="x")

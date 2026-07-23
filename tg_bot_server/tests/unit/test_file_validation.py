import pytest

from backend.common.domain import ValidationError
from backend.modules.files.application.image_validation import validate_image_content


@pytest.mark.unit
@pytest.mark.parametrize(
    ("content", "content_type", "message"),
    [
        (b"", "image/png", "empty"),
        (b"not-an-image", "image/png", "signature"),
        (b"\x89PNG\r\n\x1a\nlarge", "image/png", "large"),
    ],
)
def test_image_validation_rejects_invalid_content(
    content: bytes,
    content_type: str,
    message: str,
) -> None:
    max_bytes = 1 if message == "large" else 1024

    with pytest.raises(ValidationError):
        validate_image_content(
            content=content,
            content_type=content_type,
            max_bytes=max_bytes,
        )


@pytest.mark.unit
def test_image_validation_accepts_matching_png_signature() -> None:
    validate_image_content(
        content=b"\x89PNG\r\n\x1a\ncontent",
        content_type="image/png",
        max_bytes=1024,
    )

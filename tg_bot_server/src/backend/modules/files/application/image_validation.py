from backend.common.domain import ValidationError

IMAGE_SIGNATURES = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/webp": b"RIFF",
}


def validate_image_content(
    *,
    content: bytes,
    content_type: str,
    max_bytes: int,
) -> None:
    if not content:
        raise ValidationError("Image file is empty")
    if len(content) > max_bytes:
        raise ValidationError("Image file is too large")
    signature = IMAGE_SIGNATURES.get(content_type)
    if signature is None or not content.startswith(signature):
        raise ValidationError("Image MIME type does not match file signature")
    if content_type == "image/webp" and content[8:12] != b"WEBP":
        raise ValidationError("Image file signature is invalid")

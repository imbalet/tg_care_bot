import secrets
from typing import Annotated

from fastapi import Header

from backend.bootstrap.settings import get_settings
from backend.common.domain import AuthenticationError


async def require_service_key(
    service_key: Annotated[str | None, Header(alias="X-Service-Key")] = None,
) -> None:
    expected_key = get_settings().service_key
    if service_key is None or not secrets.compare_digest(service_key, expected_key):
        raise AuthenticationError()


__all__ = ["require_service_key"]

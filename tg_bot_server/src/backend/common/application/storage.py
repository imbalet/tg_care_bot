from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    object_key: str
    content_type: str
    size_bytes: int


class ObjectStorage(Protocol):
    async def put(
        self,
        object_key: str,
        content: bytes,
        content_type: str,
    ) -> StoredObject:
        pass

    async def delete(self, object_key: str) -> None:
        pass

    async def create_download_url(self, object_key: str) -> str:
        pass


__all__ = ["ObjectStorage", "StoredObject"]

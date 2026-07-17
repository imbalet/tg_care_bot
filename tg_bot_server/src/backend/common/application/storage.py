from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    storage_key: str
    content_type: str
    size_bytes: int


class ObjectStorage(Protocol):
    async def put(
        self,
        storage_key: str,
        content: bytes,
        content_type: str,
    ) -> StoredObject:
        pass

    async def delete(self, storage_key: str) -> None:
        pass

    async def create_download_url(self, storage_key: str) -> str:
        pass

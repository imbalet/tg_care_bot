from typing import Protocol
from uuid import UUID

from .dto import CreateFileCommand, CreateFileLinkCommand, FileDTO, FileLinkDTO


class FileRepository(Protocol):
    async def get(self, file_id: UUID) -> FileDTO | None:
        pass

    async def add_file(self, command: CreateFileCommand) -> FileDTO:
        pass

    async def add_link(self, command: CreateFileLinkCommand) -> FileLinkDTO:
        pass

    async def replace_avatar_link(
        self,
        *,
        file_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> FileLinkDTO:
        pass

    async def mark_deleted(self, file_id: UUID) -> None:
        pass


class FileQueryService(Protocol):
    async def list_links_for_entity(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        purpose: str | None = None,
    ) -> tuple[FileLinkDTO, ...]:
        pass


__all__ = ["FileQueryService", "FileRepository"]

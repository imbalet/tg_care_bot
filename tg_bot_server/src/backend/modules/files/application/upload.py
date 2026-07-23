from dataclasses import dataclass
from hashlib import sha256

from backend.common.application import ObjectStorage, new_uuid
from backend.common.domain import NotFoundError, ValidationError
from backend.modules.customers.application.interfaces import CustomerRepository
from backend.modules.files.application.dto import (
    CreateFileCommand,
    CreateFileLinkCommand,
    FileDTO,
)
from backend.modules.files.application.interfaces import FileRepository
from backend.modules.performers.application.interfaces import PerformerRepository

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class UploadActorFileCommand:
    actor_type: str
    telegram_id: int
    content: bytes
    content_type: str
    original_name: str | None


class UploadActorFileUseCase:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        performer_repository: PerformerRepository,
        file_repository: FileRepository,
        storage: ObjectStorage,
    ) -> None:
        self._customers = customer_repository
        self._performers = performer_repository
        self._files = file_repository
        self._storage = storage

    async def execute(self, command: UploadActorFileCommand) -> FileDTO:
        if not command.content or len(command.content) > MAX_UPLOAD_BYTES:
            raise ValidationError("File is empty or too large")
        if command.content_type not in {
            "image/jpeg",
            "image/png",
            "image/webp",
            "application/pdf",
        }:
            raise ValidationError("File type is not allowed")
        if not _matches_signature(command.content, command.content_type):
            raise ValidationError("File signature does not match MIME type")
        if command.actor_type == "customer":
            customer = await self._customers.get_by_telegram_id(command.telegram_id)
            if customer is None:
                raise NotFoundError("Account not found")
            actor_id = customer.id
            entity_type = "customer"
        else:
            performer = await self._performers.get_performer_by_telegram_id(
                command.telegram_id
            )
            if performer is None:
                raise NotFoundError("Account not found")
            actor_id = performer.id
            entity_type = "performer"
        extension = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "application/pdf": ".pdf",
        }[command.content_type]
        storage_key = f"uploads/{entity_type}/{actor_id}/{new_uuid()}{extension}"
        stored = await self._storage.put(
            storage_key, command.content, command.content_type
        )
        file = await self._files.add_file(
            CreateFileCommand(
                telegram_file_id=None,
                bucket=stored.bucket,
                storage_key=stored.storage_key,
                original_name=command.original_name,
                mime_type=command.content_type,
                size_bytes=stored.size_bytes,
                checksum=sha256(command.content).hexdigest(),
            )
        )
        await self._files.add_link(
            CreateFileLinkCommand(
                file_id=file.id,
                entity_type=entity_type,
                entity_id=actor_id,
                purpose="other",
            )
        )
        return file


def _matches_signature(content: bytes, content_type: str) -> bool:
    signatures = {
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
        "application/pdf": content.startswith(b"%PDF-"),
    }
    return signatures[content_type]

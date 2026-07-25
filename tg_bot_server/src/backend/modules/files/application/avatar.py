from dataclasses import dataclass
from hashlib import sha256

from backend.common.application import ObjectStorage, new_uuid
from backend.common.domain import NotFoundError, ValidationError
from backend.modules.files.application.dto import CreateFileCommand, FileDTO
from backend.modules.files.application.interfaces import FileRepository
from backend.modules.performers.application.interfaces import PerformerRepository

MAX_AVATAR_BYTES = 5 * 1024 * 1024
AVATAR_SIGNATURES = {
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/webp": (b"RIFF", ".webp"),
}


@dataclass(frozen=True)
class UploadPerformerAvatarCommand:
    telegram_id: int
    content: bytes
    content_type: str
    original_name: str | None
    telegram_file_id: str | None = None


class UploadPerformerAvatarUseCase:
    def __init__(
        self,
        performer_repository: PerformerRepository,
        file_repository: FileRepository,
        storage: ObjectStorage,
    ) -> None:
        self._performer_repository = performer_repository
        self._file_repository = file_repository
        self._storage = storage

    async def execute(self, command: UploadPerformerAvatarCommand) -> FileDTO:
        performer = await self._performer_repository.get_performer_by_telegram_id(
            command.telegram_id,
        )
        if performer is None:
            raise NotFoundError("Performer is not registered")
        mime_type, extension = validate_avatar_file(
            content=command.content,
            content_type=command.content_type,
        )
        storage_key = f"avatars/performers/{performer.id}/{new_uuid()}{extension}"
        stored = await self._storage.put(storage_key, command.content, mime_type)
        file = await self._file_repository.add_file(
            CreateFileCommand(
                telegram_file_id=command.telegram_file_id,
                bucket=stored.bucket,
                storage_key=stored.storage_key,
                original_name=command.original_name,
                mime_type=mime_type,
                size_bytes=stored.size_bytes,
                checksum=sha256(command.content).hexdigest(),
            ),
        )
        previous_file = await self._file_repository.get_avatar_for_entity(
            entity_type="performer",
            entity_id=performer.id,
        )
        if previous_file is not None:
            if previous_file.storage_key is not None:
                await self._storage.delete(previous_file.storage_key)
            await self._file_repository.delete_avatar_link(
                entity_type="performer",
                entity_id=performer.id,
            )
            await self._file_repository.mark_deleted(previous_file.id)
        await self._file_repository.replace_avatar_link(
            file_id=file.id,
            entity_type="performer",
            entity_id=performer.id,
        )
        return file


def validate_avatar_file(*, content: bytes, content_type: str) -> tuple[str, str]:
    if not content:
        raise ValidationError("Avatar file is empty")
    if len(content) > MAX_AVATAR_BYTES:
        raise ValidationError("Avatar file is too large")
    for mime_type, (signature, extension) in AVATAR_SIGNATURES.items():
        if content.startswith(signature):
            if content_type != mime_type:
                raise ValidationError("Avatar MIME type does not match file signature")
            if mime_type == "image/webp" and content[8:12] != b"WEBP":
                raise ValidationError("Avatar file signature is invalid")
            return mime_type, extension
    raise ValidationError("Avatar file type is not allowed")

from backend.modules.files.application import FileDTO, FileLinkDTO

from .models import FileLinkModel, FileModel


def file_to_dto(model: FileModel) -> FileDTO:
    return FileDTO(
        id=model.id,
        telegram_file_id=model.telegram_file_id,
        bucket=model.bucket,
        storage_key=model.storage_key,
        original_name=model.original_name,
        mime_type=model.mime_type,
        size_bytes=model.size_bytes,
        checksum=model.checksum,
        status=model.status,
        created_at=model.created_at,
        deleted_at=model.deleted_at,
    )


def link_to_dto(model: FileLinkModel) -> FileLinkDTO:
    return FileLinkDTO(
        id=model.id,
        file_id=model.file_id,
        entity_type=model.entity_type,
        entity_id=model.entity_id,
        purpose=model.purpose,
        sort_order=model.sort_order,
        created_at=model.created_at,
    )

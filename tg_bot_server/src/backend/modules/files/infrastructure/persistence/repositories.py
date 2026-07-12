from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import utc_now
from backend.common.domain import NotFoundError, ValidationError
from backend.modules.files.application import (
    CreateFileCommand,
    CreateFileLinkCommand,
    FileDTO,
    FileLinkDTO,
)

from .models import FileLinkModel, FileModel

FILE_STATUSES = frozenset(("uploaded", "deleted", "failed"))
FILE_ENTITY_TYPES = frozenset(
    ("customer", "performer", "order_report", "dispute", "complaint"),
)
FILE_PURPOSES = frozenset(
    (
        "avatar",
        "report_photo",
        "dispute_attachment",
        "complaint_attachment",
        "admin_attachment",
        "other",
    ),
)


def _file_to_dto(model: FileModel) -> FileDTO:
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


def _link_to_dto(model: FileLinkModel) -> FileLinkDTO:
    return FileLinkDTO(
        id=model.id,
        file_id=model.file_id,
        entity_type=model.entity_type,
        entity_id=model.entity_id,
        purpose=model.purpose,
        sort_order=model.sort_order,
        created_at=model.created_at,
    )


class SqlAlchemyFileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, file_id: UUID) -> FileDTO | None:
        model = await self._session.get(FileModel, file_id)
        return _file_to_dto(model) if model is not None else None

    async def add_file(self, command: CreateFileCommand) -> FileDTO:
        if command.status not in FILE_STATUSES:
            raise ValidationError("Invalid file status")
        model = FileModel(
            telegram_file_id=command.telegram_file_id,
            bucket=command.bucket,
            storage_key=command.storage_key,
            original_name=command.original_name,
            mime_type=command.mime_type,
            size_bytes=command.size_bytes,
            checksum=command.checksum,
            status=command.status,
        )
        self._session.add(model)
        await self._session.flush()
        return _file_to_dto(model)

    async def add_link(self, command: CreateFileLinkCommand) -> FileLinkDTO:
        if command.entity_type not in FILE_ENTITY_TYPES:
            raise ValidationError("Invalid file entity type")
        if command.purpose not in FILE_PURPOSES:
            raise ValidationError("Invalid file purpose")
        model = FileLinkModel(
            file_id=command.file_id,
            entity_type=command.entity_type,
            entity_id=command.entity_id,
            purpose=command.purpose,
            sort_order=command.sort_order,
        )
        self._session.add(model)
        await self._session.flush()
        return _link_to_dto(model)

    async def replace_avatar_link(
        self,
        *,
        file_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> FileLinkDTO:
        await self._session.execute(
            delete(FileLinkModel).where(
                FileLinkModel.entity_type == entity_type,
                FileLinkModel.entity_id == entity_id,
                FileLinkModel.purpose == "avatar",
            ),
        )
        return await self.add_link(
            CreateFileLinkCommand(
                file_id=file_id,
                entity_type=entity_type,
                entity_id=entity_id,
                purpose="avatar",
            ),
        )

    async def mark_deleted(self, file_id: UUID) -> None:
        model = await self._session.get(FileModel, file_id)
        if model is None:
            raise NotFoundError("File not found")
        model.status = "deleted"
        model.deleted_at = utc_now()

    async def get_avatar_for_entity(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
    ) -> FileDTO | None:
        result = await self._session.execute(
            select(FileModel)
            .join(FileLinkModel, FileLinkModel.file_id == FileModel.id)
            .where(
                FileLinkModel.entity_type == entity_type,
                FileLinkModel.entity_id == entity_id,
                FileLinkModel.purpose == "avatar",
                FileModel.deleted_at.is_(None),
            ),
        )
        model = result.scalar_one_or_none()
        return _file_to_dto(model) if model is not None else None

    async def delete_avatar_link(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
    ) -> None:
        await self._session.execute(
            delete(FileLinkModel).where(
                FileLinkModel.entity_type == entity_type,
                FileLinkModel.entity_id == entity_id,
                FileLinkModel.purpose == "avatar",
            ),
        )

    async def list_links_for_entity(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        purpose: str | None = None,
    ) -> tuple[FileLinkDTO, ...]:
        statement = select(FileLinkModel).where(
            FileLinkModel.entity_type == entity_type,
            FileLinkModel.entity_id == entity_id,
        )
        if purpose is not None:
            statement = statement.where(FileLinkModel.purpose == purpose)
        statement = statement.order_by(
            FileLinkModel.sort_order,
            FileLinkModel.created_at,
        )
        result = await self._session.execute(statement)
        return tuple(_link_to_dto(model) for model in result.scalars())


__all__ = [
    "FILE_ENTITY_TYPES",
    "FILE_PURPOSES",
    "FILE_STATUSES",
    "SqlAlchemyFileRepository",
]

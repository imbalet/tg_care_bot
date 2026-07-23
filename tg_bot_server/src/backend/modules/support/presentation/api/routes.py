from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.domain import ValidationError
from backend.common.presentation import require_service_key
from backend.modules.admin.presentation.api.routes import (
    get_current_admin,
    require_admin_csrf,
)
from backend.modules.admin.presentation.api.schemas import AdminResponse
from backend.modules.files.application import UploadActorFileCommand

from .schemas import (
    AccountDeletionPreflightResponse,
    ContactRequestResponse,
    CreateComplaintRequest,
    CreateContactRequest,
    CreateDisputeRequest,
    CreateSupportRequest,
    FileUploadResponse,
    SupportFileResponse,
    SupportRecordPageResponse,
    SupportRecordResponse,
    UpdateSupportRecordRequest,
)

customer_router = APIRouter(
    prefix="/api/customers",
    tags=["customer-support"],
    dependencies=[Depends(require_service_key)],
)
performer_router = APIRouter(
    prefix="/api/performers",
    tags=["performer-support"],
    dependencies=[Depends(require_service_key)],
)
admin_router = APIRouter(prefix="/admin/support", tags=["admin-support"])


async def _deletion_preflight(
    container: Container,
    actor_type: str,
    telegram_id: int,
) -> AccountDeletionPreflightResponse:
    blockers = await container.support.deletion_preflight(
        actor_type=actor_type,
        telegram_id=telegram_id,
    )
    return AccountDeletionPreflightResponse(
        can_delete=not blockers,
        blockers=blockers,
    )


@customer_router.get(
    "/by-telegram/{telegram_id}/deletion-preflight",
)
async def customer_deletion_preflight(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> AccountDeletionPreflightResponse:
    return await _deletion_preflight(container, "customer", telegram_id)


@performer_router.get(
    "/by-telegram/{telegram_id}/deletion-preflight",
)
async def performer_deletion_preflight(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> AccountDeletionPreflightResponse:
    return await _deletion_preflight(container, "performer", telegram_id)


def _record_response(
    record: Any, kind: str, files: list[dict[str, Any]] | None = None
) -> SupportRecordResponse:
    return SupportRecordResponse(
        id=record.id,
        kind=kind,
        customer_id=getattr(record, "customer_id", None),
        performer_id=getattr(record, "performer_id", None),
        order_id=getattr(record, "order_id", None),
        direction=getattr(record, "direction", None),
        type=getattr(record, "type", None),
        category=getattr(record, "category", None),
        text=getattr(record, "text", None),
        status=record.status,
        blockers=getattr(record, "blockers", []),
        admin_comment=record.admin_comment,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
        resolved_at=record.resolved_at.isoformat()
        if getattr(record, "resolved_at", None)
        else None,
        files=[SupportFileResponse(**file) for file in files or []],
    )


async def _user_list(
    container: Container,
    actor_type: str,
    telegram_id: int,
    kind: str,
    status: str | None,
    page: int,
    page_size: int,
) -> SupportRecordPageResponse:
    if page < 1 or page_size < 1 or page_size > 100:
        raise ValidationError("Invalid pagination")
    records, total = await container.support.list_support_records(
        actor_type=actor_type,
        telegram_id=telegram_id,
        record_kind=kind,
        status=status,
        page=page,
        page_size=page_size,
    )
    return SupportRecordPageResponse(
        items=[_record_response(record, kind) for record in records],
        page=page,
        page_size=page_size,
        total=total,
    )


async def _admin_list(
    container: Container,
    kind: str,
    status: str | None,
    page: int,
    page_size: int,
) -> SupportRecordPageResponse:
    if page < 1 or page_size < 1 or page_size > 100:
        raise ValidationError("Invalid pagination")
    records, total = await container.support.list_admin_support_records(
        record_kind=kind,
        status=status,
        page=page,
        page_size=page_size,
    )
    return SupportRecordPageResponse(
        items=[_record_response(record, kind) for record in records],
        page=page,
        page_size=page_size,
        total=total,
    )


@customer_router.post("/by-telegram/{telegram_id}/support-requests", status_code=201)
async def create_customer_support(
    telegram_id: int,
    request: CreateSupportRequest,
    container: Annotated[Container, Depends(get_container)],
) -> SupportRecordResponse:
    record = await container.support.create_support_request(
        actor_type="customer",
        telegram_id=telegram_id,
        order_id=request.order_id,
        request_type=request.type,
        text=request.text,
        file_ids=request.file_ids,
    )
    return _record_response(record, "support")


@performer_router.post("/by-telegram/{telegram_id}/support-requests", status_code=201)
async def create_performer_support(
    telegram_id: int,
    request: CreateSupportRequest,
    container: Annotated[Container, Depends(get_container)],
) -> SupportRecordResponse:
    record = await container.support.create_support_request(
        actor_type="performer",
        telegram_id=telegram_id,
        order_id=request.order_id,
        request_type=request.type,
        text=request.text,
        file_ids=request.file_ids,
    )
    return _record_response(record, "support")


@customer_router.post("/by-telegram/{telegram_id}/complaints", status_code=201)
async def create_customer_complaint(
    telegram_id: int,
    request: CreateComplaintRequest,
    container: Annotated[Container, Depends(get_container)],
) -> SupportRecordResponse:
    record = await container.support.create_complaint(
        actor_type="customer",
        telegram_id=telegram_id,
        order_id=request.order_id,
        category=request.category,
        text=request.text,
        file_ids=request.file_ids,
    )
    return _record_response(record, "complaint")


@customer_router.post("/by-telegram/{telegram_id}/disputes", status_code=201)
async def create_customer_dispute(
    telegram_id: int,
    request: CreateDisputeRequest,
    container: Annotated[Container, Depends(get_container)],
) -> SupportRecordResponse:
    record = await container.support.create_dispute(
        telegram_id=telegram_id,
        order_id=request.order_id,
        text=request.text,
        file_ids=request.file_ids,
    )
    return _record_response(record, "dispute")


@customer_router.post("/by-telegram/{telegram_id}/contact-requests", status_code=201)
async def create_customer_contact_request(
    telegram_id: int,
    request: CreateContactRequest,
    container: Annotated[Container, Depends(get_container)],
) -> ContactRequestResponse:
    record = await container.support.create_contact_request(
        telegram_id=telegram_id,
        order_id=request.order_id,
    )
    return ContactRequestResponse(
        id=record.id,
        order_id=record.order_id,
        performer_id=record.performer_id,
        requested_method=record.requested_method,
        status=record.status,
        failure_reason=record.failure_reason,
    )


@customer_router.post("/by-telegram/{telegram_id}/files", status_code=201)
async def upload_customer_file(
    telegram_id: int,
    file: Annotated[UploadFile, File()],
    container: Annotated[Container, Depends(get_container)],
) -> FileUploadResponse:
    stored = await container.customers.upload_customer_file(
        UploadActorFileCommand(
            actor_type="customer",
            telegram_id=telegram_id,
            content=await file.read(),
            content_type=file.content_type or "",
            original_name=file.filename,
        )
    )
    return FileUploadResponse(
        id=stored.id,
        original_name=stored.original_name,
        mime_type=stored.mime_type,
        size_bytes=stored.size_bytes,
        status=stored.status,
    )


@performer_router.post("/by-telegram/{telegram_id}/files", status_code=201)
async def upload_performer_file(
    telegram_id: int,
    file: Annotated[UploadFile, File()],
    container: Annotated[Container, Depends(get_container)],
) -> FileUploadResponse:
    stored = await container.performers.upload_performer_file(
        UploadActorFileCommand(
            actor_type="performer",
            telegram_id=telegram_id,
            content=await file.read(),
            content_type=file.content_type or "",
            original_name=file.filename,
        )
    )
    return FileUploadResponse(
        id=stored.id,
        original_name=stored.original_name,
        mime_type=stored.mime_type,
        size_bytes=stored.size_bytes,
        status=stored.status,
    )


@performer_router.post("/by-telegram/{telegram_id}/complaints", status_code=201)
async def create_performer_complaint(
    telegram_id: int,
    request: CreateComplaintRequest,
    container: Annotated[Container, Depends(get_container)],
) -> SupportRecordResponse:
    record = await container.support.create_complaint(
        actor_type="performer",
        telegram_id=telegram_id,
        order_id=request.order_id,
        category=request.category,
        text=request.text,
        file_ids=request.file_ids,
    )
    return _record_response(record, "complaint")


@customer_router.post("/by-telegram/{telegram_id}/deletion-requests", status_code=201)
async def create_customer_deletion(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> SupportRecordResponse:
    record = await container.support.create_deletion_request(
        actor_type="customer", telegram_id=telegram_id
    )
    return _record_response(record, "deletion")


@performer_router.post("/by-telegram/{telegram_id}/deletion-requests", status_code=201)
async def create_performer_deletion(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> SupportRecordResponse:
    record = await container.support.create_deletion_request(
        actor_type="performer", telegram_id=telegram_id
    )
    return _record_response(record, "deletion")


def _register_user_reads(router: APIRouter, actor_type: str) -> None:
    @router.get("/by-telegram/{telegram_id}/support-requests")
    async def list_support(
        telegram_id: int,
        container: Annotated[Container, Depends(get_container)],
        status: str | None = Query(default=None),
        page: int = 1,
        page_size: int = 50,
    ) -> SupportRecordPageResponse:
        return await _user_list(
            container, actor_type, telegram_id, "support", status, page, page_size
        )

    @router.get("/by-telegram/{telegram_id}/complaints")
    async def list_complaints(
        telegram_id: int,
        container: Annotated[Container, Depends(get_container)],
        status: str | None = Query(default=None),
        page: int = 1,
        page_size: int = 50,
    ) -> SupportRecordPageResponse:
        return await _user_list(
            container, actor_type, telegram_id, "complaint", status, page, page_size
        )

    @router.get("/by-telegram/{telegram_id}/disputes")
    async def list_disputes(
        telegram_id: int,
        container: Annotated[Container, Depends(get_container)],
        status: str | None = Query(default=None),
        page: int = 1,
        page_size: int = 50,
    ) -> SupportRecordPageResponse:
        return await _user_list(
            container, actor_type, telegram_id, "dispute", status, page, page_size
        )

    @router.get("/by-telegram/{telegram_id}/deletion-requests")
    async def list_deletions(
        telegram_id: int,
        container: Annotated[Container, Depends(get_container)],
        status: str | None = Query(default=None),
        page: int = 1,
        page_size: int = 50,
    ) -> SupportRecordPageResponse:
        return await _user_list(
            container, actor_type, telegram_id, "deletion", status, page, page_size
        )

    @router.get("/by-telegram/{telegram_id}/{kind}/{record_id}")
    async def get_record(
        telegram_id: int,
        kind: str,
        record_id: UUID,
        container: Annotated[Container, Depends(get_container)],
    ) -> SupportRecordResponse:
        record, files = await container.support.get_support_record(
            record_kind=kind,
            record_id=record_id,
            actor_type=actor_type,
            telegram_id=telegram_id,
        )
        return _record_response(record, kind, files)


_register_user_reads(customer_router, "customer")
_register_user_reads(performer_router, "performer")


@admin_router.get("/{kind}")
async def list_admin_records(
    kind: str,
    container: Annotated[Container, Depends(get_container)],
    _current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
    status: str | None = Query(default=None),
    page: int = 1,
    page_size: int = 50,
) -> SupportRecordPageResponse:
    return await _admin_list(container, kind, status, page, page_size)


@admin_router.get("/{kind}/{record_id}")
async def get_admin_record(
    kind: str,
    record_id: UUID,
    container: Annotated[Container, Depends(get_container)],
    _current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
) -> SupportRecordResponse:
    record, files = await container.support.get_support_record(
        record_kind=kind, record_id=record_id
    )
    return _record_response(record, kind, files)


@admin_router.patch("/{kind}/{record_id}")
async def update_admin_record(
    kind: str,
    record_id: UUID,
    request: UpdateSupportRecordRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> SupportRecordResponse:
    record = await container.support.update_support_record(
        record_kind=kind,
        record_id=record_id,
        status=request.status,
        admin_comment=request.admin_comment,
        admin_id=UUID(current[0].id),
    )
    return _record_response(record, kind)

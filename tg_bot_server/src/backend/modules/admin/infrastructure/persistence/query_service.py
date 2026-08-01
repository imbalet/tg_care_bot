from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect

from backend.modules.addresses.infrastructure import AddressModel
from backend.modules.admin.infrastructure.persistence.audit_models import (
    AdminAuditLogModel,
)
from backend.modules.admin.infrastructure.persistence.violation_models import (
    AdminViolationModel,
)
from backend.modules.care_objects.infrastructure import CareObjectModel
from backend.modules.catalog.infrastructure import (
    BusinessSettingModel,
    CityModel,
    DistrictModel,
    LegalDocumentModel,
    ObjectCountMultiplierModel,
    ServiceCategoryModel,
    ServiceModel,
    ServiceOptionModel,
)
from backend.modules.customers.infrastructure import CustomerModel
from backend.modules.files.infrastructure import FileLinkModel, FileModel
from backend.modules.notifications.infrastructure.persistence.models import (
    NotificationModel,
)
from backend.modules.orders.infrastructure.exports import (
    OrderAddressSnapshotModel,
    OrderCareObjectModel,
    OrderMatchModel,
    OrderModel,
    OrderOptionValueModel,
    OrderReportModel,
    OrderStatusHistoryModel,
)
from backend.modules.payments.infrastructure import PaymentModel, RefundModel
from backend.modules.performers.infrastructure import (
    PerformerCalendarOverrideModel,
    PerformerInvitationModel,
    PerformerModel,
    PerformerScheduleModel,
    PerformerServiceModel,
)
from backend.modules.support.infrastructure import (
    AccountDeletionRequestModel,
    ComplaintModel,
    DisputeModel,
    SupportRequestModel,
)


class AdminResourceNotFound(LookupError):
    pass


_RESOURCE_MODELS: dict[str, type[Any]] = {
    "customers": CustomerModel,
    "performers": PerformerModel,
    "invitations": PerformerInvitationModel,
    "performer-services": PerformerServiceModel,
    "schedules": PerformerScheduleModel,
    "calendar": PerformerCalendarOverrideModel,
    "orders": OrderModel,
    "matches": OrderMatchModel,
    "order-objects": OrderCareObjectModel,
    "order-options": OrderOptionValueModel,
    "order-history": OrderStatusHistoryModel,
    "reports": OrderReportModel,
    "payments": PaymentModel,
    "refunds": RefundModel,
    "support": SupportRequestModel,
    "complaints": ComplaintModel,
    "disputes": DisputeModel,
    "deletions": AccountDeletionRequestModel,
    "files": FileModel,
    "file-links": FileLinkModel,
    "settings": BusinessSettingModel,
    "cities": CityModel,
    "districts": DistrictModel,
    "service-categories": ServiceCategoryModel,
    "services": ServiceModel,
    "service-options": ServiceOptionModel,
    "multipliers": ObjectCountMultiplierModel,
    "legal-documents": LegalDocumentModel,
    "audit": AdminAuditLogModel,
    "violations": AdminViolationModel,
    "notifications": NotificationModel,
}

_SENSITIVE_FIELDS = {"password_hash", "storage_key", "idempotency_key"}


def _json_value(value: Any) -> Any:
    if isinstance(value, UUID | datetime | date | time):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _model_dict(instance: Any) -> dict[str, Any]:
    return {
        column.key: _json_value(getattr(instance, column.key))
        for column in inspect(instance).mapper.column_attrs
        if column.key not in _SENSITIVE_FIELDS
    }


class SqlAlchemyAdminQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _model(resource: str) -> type[Any]:
        try:
            return _RESOURCE_MODELS[resource]
        except KeyError as exc:
            raise AdminResourceNotFound(resource) from exc

    @staticmethod
    def _with_filters(
        statement: Select[Any],
        model: type[Any],
        *,
        query: str | None,
        status: str | None,
    ) -> Select[Any]:
        if status and hasattr(model, "status"):
            statement = statement.where(model.status == status)
        if query:
            pattern = f"%{query}%"
            clauses = []
            for column in inspect(model).columns:
                if column.key in {"password_hash", "storage_key"}:
                    continue
                if str(column.type).upper().startswith(("TEXT", "VARCHAR")):
                    clauses.append(column.ilike(pattern))
            if clauses:
                statement = statement.where(or_(*clauses))
        return statement

    async def list_resources(
        self,
        resource: str,
        *,
        page: int,
        page_size: int,
        query: str | None = None,
        status: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        model = self._model(resource)
        statement = self._with_filters(select(model), model, query=query, status=status)
        count_statement = self._with_filters(
            select(func.count()).select_from(model),
            model,
            query=query,
            status=status,
        )
        total = int(await self._session.scalar(count_statement) or 0)
        if hasattr(model, "created_at"):
            statement = statement.order_by(model.created_at.desc())
        elif hasattr(model, "updated_at"):
            statement = statement.order_by(model.updated_at.desc())
        result = await self._session.scalars(
            statement.offset((page - 1) * page_size).limit(page_size)
        )
        return [_model_dict(item) for item in result], total

    async def get(self, resource: str, entity_id: UUID) -> dict[str, Any]:
        model = self._model(resource)
        item = await self._session.get(model, entity_id)
        if item is None:
            raise AdminResourceNotFound(f"{resource}/{entity_id}")
        related: dict[str, list[dict[str, Any]]] = {}
        if resource == "customers":
            related["care_objects"] = await self._related(
                CareObjectModel, "customer_id", entity_id
            )
            related["addresses"] = await self._related(
                AddressModel, "customer_id", entity_id
            )
            related["orders"] = await self._related(
                OrderModel, "customer_id", entity_id
            )
            related["violations"] = await self._related(
                AdminViolationModel, "customer_id", entity_id
            )
        elif resource == "performers":
            related["services"] = await self._related(
                PerformerServiceModel, "performer_id", entity_id
            )
            related["schedules"] = await self._related(
                PerformerScheduleModel, "performer_id", entity_id
            )
            related["calendar"] = await self._related(
                PerformerCalendarOverrideModel, "performer_id", entity_id
            )
            related["addresses"] = await self._related(
                AddressModel, "performer_id", entity_id
            )
            related["orders"] = await self._related(
                OrderModel, "selected_performer_id", entity_id
            )
            related["violations"] = await self._related(
                AdminViolationModel, "performer_id", entity_id
            )
        elif resource == "orders":
            related["matches"] = await self._related(
                OrderMatchModel, "order_id", entity_id
            )
            related["payments"] = await self._related(
                PaymentModel, "order_id", entity_id
            )
            related["refunds"] = await self._related(RefundModel, "order_id", entity_id)
            related["reports"] = await self._related(
                OrderReportModel, "order_id", entity_id
            )
            related["history"] = await self._related(
                OrderStatusHistoryModel, "order_id", entity_id
            )
            related["address_snapshot"] = await self._related(
                OrderAddressSnapshotModel, "order_id", entity_id
            )
        elif resource == "payments":
            related["refunds"] = await self._related(
                RefundModel, "payment_id", entity_id
            )
        elif resource == "reports":
            related["files"] = await self._file_links(entity_id, "order_report")
        elif resource in {"support", "complaints", "disputes", "deletions"}:
            related["files"] = await self._file_links(entity_id, resource)
            order_id = getattr(item, "order_id", None)
            customer_id = getattr(item, "customer_id", None)
            performer_id = getattr(item, "performer_id", None)
            if order_id is not None:
                order = await self._session.get(OrderModel, order_id)
                if order is not None:
                    related["order"] = [_model_dict(order)]
                    related["payments"] = await self._related(
                        PaymentModel, "order_id", order_id
                    )
                    related["refunds"] = await self._related(
                        RefundModel, "order_id", order_id
                    )
                    report_rows = await self._related(
                        OrderReportModel, "order_id", order_id
                    )
                    for report in report_rows:
                        report["files"] = await self._file_links(
                            UUID(report["id"]), "order_report"
                        )
                    related["reports"] = report_rows
                    customer_id = customer_id or order.customer_id
                    performer_id = performer_id or order.selected_performer_id
            if customer_id is not None:
                customer = await self._session.get(CustomerModel, customer_id)
                if customer is not None:
                    related["customer"] = [_model_dict(customer)]
                    related["customer_violations"] = await self._related(
                        AdminViolationModel, "customer_id", customer_id
                    )
            if performer_id is not None:
                performer = await self._session.get(PerformerModel, performer_id)
                if performer is not None:
                    related["performer"] = [_model_dict(performer)]
                    related["performer_violations"] = await self._related(
                        AdminViolationModel, "performer_id", performer_id
                    )
        return {"item": _model_dict(item), "related": related}

    async def _file_links(self, entity_id: UUID, resource: str) -> list[dict[str, Any]]:
        entity_type = "support_request" if resource == "support" else resource
        rows = await self._session.execute(
            select(FileLinkModel, FileModel)
            .join(FileModel, FileModel.id == FileLinkModel.file_id)
            .where(
                FileLinkModel.entity_type == entity_type,
                FileLinkModel.entity_id == entity_id,
            )
            .order_by(FileLinkModel.sort_order, FileLinkModel.created_at),
        )
        result: list[dict[str, Any]] = []
        for link, file in rows:
            result.append(
                {
                    "id": str(file.id),
                    "link_id": str(link.id),
                    "entity_type": link.entity_type,
                    "purpose": link.purpose,
                    "original_name": file.original_name,
                    "mime_type": file.mime_type,
                    "size_bytes": file.size_bytes,
                    "status": file.status,
                    "created_at": file.created_at.isoformat(),
                }
            )
        return result

    async def dashboard(self, *, admin_id: UUID | None = None) -> dict[str, Any]:
        queue_specs = {
            "performer_moderation": (
                PerformerModel,
                PerformerModel.status.in_(("invited", "profile_pending")),
            ),
            "orders_attention": (
                OrderModel,
                OrderModel.requires_admin_attention.is_(True),
            ),
            "cases": (None, None),
            "finance": (None, None),
            "deletions": (
                AccountDeletionRequestModel,
                AccountDeletionRequestModel.status.in_(("open", "in_progress")),
            ),
        }
        metrics = {
            "performer_moderation": await self._count(
                PerformerModel,
                PerformerModel.status.in_(("invited", "profile_pending")),
            ),
            "orders_attention": await self._count(
                OrderModel,
                OrderModel.requires_admin_attention.is_(True),
            ),
            "open_disputes": await self._count(
                DisputeModel,
                DisputeModel.status.in_(("open", "in_progress")),
            ),
            "open_complaints": await self._count(
                ComplaintModel,
                ComplaintModel.status.in_(("open", "in_progress")),
            ),
            "finance": (
                await self._count(
                    PaymentModel,
                    or_(
                        PaymentModel.failure_code.is_not(None),
                        PaymentModel.status.in_(("failed", "pending")),
                    ),
                )
                + await self._count(
                    RefundModel,
                    RefundModel.status.in_(("pending", "failed")),
                )
                + await self._count(
                    OrderModel,
                    OrderModel.payout_status.in_(("blocked", "failed", "ready")),
                )
            ),
            "deletions": await self._count(
                AccountDeletionRequestModel,
                AccountDeletionRequestModel.status.in_(("open", "in_progress")),
            ),
            "unread_notifications": await self._count_notifications(admin_id),
        }
        queues: dict[str, dict[str, Any]] = {}
        for name, (model, condition) in queue_specs.items():
            if model is None:
                continue
            items = await self._queue_rows(
                model,
                condition,
                resource={
                    "performer_moderation": "performers",
                    "orders_attention": "orders",
                    "deletions": "deletions",
                }[name],
                limit=8,
            )
            queues[name] = {"items": items, "total": metrics[name]}
        queues["cases"] = await self._cases_queue(limit=8)
        queues["finance"] = await self._finance_queue(limit=8)
        return {"metrics": metrics, "queues": queues}

    async def _count_notifications(self, admin_id: UUID | None) -> int:
        conditions = [
            NotificationModel.recipient_type == "admin",
            NotificationModel.read_at.is_(None),
        ]
        if admin_id is not None:
            conditions.append(
                or_(
                    NotificationModel.admin_id == admin_id,
                    NotificationModel.admin_id.is_(None),
                )
            )
        return int(
            await self._session.scalar(
                select(func.count()).select_from(NotificationModel).where(*conditions)
            )
            or 0
        )

    async def work_queue(self, queue: str, *, limit: int = 50) -> dict[str, Any]:
        if queue == "performer-moderation":
            items = await self._queue_rows(
                PerformerModel,
                PerformerModel.status.in_(("invited", "profile_pending")),
                resource="performers",
                limit=limit,
            )
            return {
                "title": "Модерация исполнителей",
                "items": items,
                "total": len(items),
            }
        if queue == "orders-attention":
            items = await self._queue_rows(
                OrderModel,
                OrderModel.requires_admin_attention.is_(True),
                resource="orders",
                limit=limit,
            )
            return {
                "title": "Заказы требуют внимания",
                "items": items,
                "total": len(items),
            }
        if queue == "cases":
            return await self._cases_queue(limit=limit)
        if queue == "finance":
            return await self._finance_queue(limit=limit)
        if queue == "deletions":
            items = await self._queue_rows(
                AccountDeletionRequestModel,
                AccountDeletionRequestModel.status.in_(("open", "in_progress")),
                resource="deletions",
                limit=limit,
            )
            return {"title": "Удаление аккаунтов", "items": items, "total": len(items)}
        raise AdminResourceNotFound(queue)

    async def _count(self, model: type[Any], condition: Any) -> int:
        return int(
            await self._session.scalar(
                select(func.count()).select_from(model).where(condition)
            )
            or 0
        )

    async def _queue_rows(
        self,
        model: type[Any],
        condition: Any,
        *,
        resource: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        order_column = getattr(
            model, "updated_at", getattr(model, "created_at", model.id)
        )
        result = await self._session.scalars(
            select(model).where(condition).order_by(order_column.desc()).limit(limit)
        )
        return [self._queue_item(item, resource) for item in result]

    async def _cases_queue(self, *, limit: int) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for model, resource in (
            (DisputeModel, "disputes"),
            (ComplaintModel, "complaints"),
            (SupportRequestModel, "support"),
        ):
            rows.extend(
                await self._queue_rows(
                    model,
                    model.status.in_(("open", "in_progress")),
                    resource=resource,
                    limit=limit,
                )
            )
        rows.sort(
            key=lambda row: row.get("updated_at") or row.get("created_at") or "",
            reverse=True,
        )
        return {
            "title": "Жалобы, споры и поддержка",
            "items": rows[:limit],
            "total": len(rows),
        }

    async def _finance_queue(self, *, limit: int) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        rows.extend(
            await self._queue_rows(
                PaymentModel,
                or_(
                    PaymentModel.failure_code.is_not(None),
                    PaymentModel.status.in_(("failed", "pending")),
                ),
                resource="payments",
                limit=limit,
            )
        )
        rows.extend(
            await self._queue_rows(
                RefundModel,
                RefundModel.status.in_(("pending", "failed")),
                resource="refunds",
                limit=limit,
            )
        )
        rows.extend(
            await self._queue_rows(
                OrderModel,
                OrderModel.payout_status.in_(("blocked", "failed", "ready")),
                resource="orders",
                limit=limit,
            )
        )
        rows.sort(
            key=lambda row: row.get("updated_at") or row.get("created_at") or "",
            reverse=True,
        )
        return {
            "title": "Платежи, возвраты и выплаты",
            "items": rows[:limit],
            "total": len(rows),
        }

    @staticmethod
    def _queue_item(item: Any, resource: str) -> dict[str, Any]:
        data = _model_dict(item)
        title = (
            data.get("full_name")
            or data.get("service_name")
            or data.get("text")
            or data.get("reason")
            or f"{resource} #{data.get('id')}"
        )
        subtitle = (
            data.get("phone") or data.get("telegram_username") or data.get("category")
        )
        return {
            "id": data.get("id"),
            "resource": resource,
            "title": str(title)[:160],
            "subtitle": str(subtitle)[:160] if subtitle else None,
            "status": data.get("status") or data.get("payout_status") or "—",
            "priority": "high" if data.get("requires_admin_attention") else "normal",
            "created_at": data.get("created_at") or data.get("updated_at"),
            "updated_at": data.get("updated_at") or data.get("created_at"),
            "data": data,
        }

    async def _related(
        self, model: type[Any], foreign_key: str, entity_id: UUID
    ) -> list[dict[str, Any]]:
        if not hasattr(model, foreign_key):
            return []
        result = await self._session.scalars(
            select(model).where(getattr(model, foreign_key) == entity_id)
        )
        return [_model_dict(item) for item in result]

from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import utc_now
from backend.common.domain import NotFoundError, ValidationError
from backend.modules.customers.infrastructure import CustomerModel
from backend.modules.files.infrastructure.persistence.models import (
    FileLinkModel,
    FileModel,
)
from backend.modules.orders.infrastructure import OrderMatchModel, OrderModel
from backend.modules.payments.infrastructure import PaymentModel, RefundModel
from backend.modules.performers.infrastructure import PerformerModel

from .models import AccountDeletionRequestModel, DisputeModel

SUPPORT_TYPES = frozenset(("technical", "payment", "order", "account", "other"))
COMPLAINT_CATEGORIES = frozenset(
    ("order_problem", "conditions_mismatch", "no_contact", "post_completion")
)
STATUSES = frozenset(("open", "in_progress", "resolved", "rejected"))
TERMINAL_STATUSES = frozenset(("resolved", "rejected"))


class SqlAlchemySupportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_actor(
        self, *, actor_type: str, telegram_id: int, for_update: bool = False
    ) -> CustomerModel | PerformerModel:
        model = CustomerModel if actor_type == "customer" else PerformerModel
        result = await self._session.execute(
            select(model).where(model.telegram_id == telegram_id).with_for_update()
            if for_update
            else select(model).where(model.telegram_id == telegram_id),
        )
        actor = result.scalar_one_or_none()
        if actor is None:
            raise NotFoundError("Account not found")
        return cast(CustomerModel | PerformerModel, actor)

    async def validate_order(
        self, *, actor_type: str, actor_id: UUID, order_id: UUID | None
    ) -> None:
        if order_id is None:
            return
        if actor_type == "customer":
            exists = await self._session.scalar(
                select(OrderModel.id).where(
                    OrderModel.id == order_id,
                    OrderModel.customer_id == actor_id,
                ),
            )
        else:
            exists = await self._session.scalar(
                select(OrderMatchModel.id).where(
                    OrderMatchModel.order_id == order_id,
                    OrderMatchModel.performer_id == actor_id,
                ),
            )
        if exists is None:
            raise ValidationError("Order is not available for this account")

    async def validate_files(
        self, *, actor_type: str, actor_id: UUID, file_ids: Sequence[UUID]
    ) -> None:
        if not file_ids:
            return
        if len(set(file_ids)) != len(file_ids):
            raise ValidationError("File IDs must be unique")
        entity_type = actor_type
        result = await self._session.execute(
            select(FileLinkModel.file_id)
            .join(FileModel, FileModel.id == FileLinkModel.file_id)
            .where(
                FileLinkModel.file_id.in_(file_ids),
                FileLinkModel.entity_type == entity_type,
                FileLinkModel.entity_id == actor_id,
                FileModel.status == "uploaded",
            ),
        )
        found = set(result.scalars())
        if found != set(file_ids):
            raise ValidationError("One or more files do not belong to the account")

    async def add_file_links(
        self,
        *,
        file_ids: Sequence[UUID],
        entity_type: str,
        entity_id: UUID,
        purpose: str,
    ) -> None:
        for sort_order, file_id in enumerate(file_ids):
            self._session.add(
                FileLinkModel(
                    file_id=file_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    purpose=purpose,
                    sort_order=sort_order,
                ),
            )

    async def list_links(self, *, entity_type: str, entity_id: UUID) -> list[FileModel]:
        result = await self._session.execute(
            select(FileModel)
            .join(FileLinkModel, FileLinkModel.file_id == FileModel.id)
            .where(
                FileLinkModel.entity_type == entity_type,
                FileLinkModel.entity_id == entity_id,
                FileModel.status == "uploaded",
            )
            .order_by(FileLinkModel.sort_order, FileLinkModel.created_at),
        )
        return list(result.scalars())

    async def blockers(
        self, *, actor_type: str, actor_id: UUID
    ) -> list[dict[str, Any]]:
        order_condition = (
            OrderModel.customer_id == actor_id
            if actor_type == "customer"
            else OrderModel.selected_performer_id == actor_id
        )
        orders = await self._session.execute(
            select(OrderModel.id, OrderModel.status).where(
                order_condition,
                OrderModel.status.in_(
                    (
                        "searching",
                        "waiting_payment",
                        "confirmed",
                        "in_progress",
                        "waiting_report",
                        "report_submitted",
                    )
                ),
            ),
        )
        blockers = [
            {"kind": "order", "id": str(row.id), "status": row.status} for row in orders
        ]
        match_condition = (
            OrderMatchModel.performer_id == actor_id
            if actor_type == "performer"
            else OrderModel.customer_id == actor_id
        )
        match_query = (
            select(OrderMatchModel.id, OrderMatchModel.status)
            .join(OrderModel, OrderModel.id == OrderMatchModel.order_id)
            .where(
                match_condition,
                OrderMatchModel.status.in_(
                    ("pending", "active", "selected", "confirmed")
                ),
            )
        )
        matches = await self._session.execute(match_query)
        blockers.extend(
            {"kind": "match", "id": str(row.id), "status": row.status}
            for row in matches
        )
        if actor_type == "performer":
            payment_query = select(PaymentModel.id, PaymentModel.status).where(
                PaymentModel.performer_id == actor_id,
                PaymentModel.status.in_(("created", "pending", "succeeded_unapplied")),
            )
            payments = await self._session.execute(payment_query)
            blockers.extend(
                {"kind": "payment", "id": str(row.id), "status": row.status}
                for row in payments
            )
        else:
            payment_query = (
                select(PaymentModel.id, PaymentModel.status)
                .join(OrderModel, OrderModel.id == PaymentModel.order_id)
                .where(
                    OrderModel.customer_id == actor_id,
                    PaymentModel.status.in_(
                        ("created", "pending", "succeeded_unapplied")
                    ),
                )
            )
            payments = await self._session.execute(payment_query)
        blockers.extend(
            {"kind": "payment", "id": str(row.id), "status": row.status}
            for row in payments
        )
        payout_query = select(OrderModel.id, OrderModel.payout_status).where(
            order_condition,
            OrderModel.payout_status.in_(
                ("blocked", "ready", "processing"),
            ),
        )
        payouts = await self._session.execute(payout_query)
        blockers.extend(
            {"kind": "payout", "id": str(row.id), "status": row.payout_status}
            for row in payouts
        )
        refund_query = (
            select(RefundModel.id, RefundModel.status)
            .join(OrderModel, OrderModel.id == RefundModel.order_id)
            .where(
                order_condition,
                RefundModel.status == "pending",
            )
        )
        refunds = await self._session.execute(refund_query)
        blockers.extend(
            {"kind": "refund", "id": str(row.id), "status": row.status}
            for row in refunds
        )
        return blockers

    async def active_deletion(
        self, *, actor_type: str, actor_id: UUID
    ) -> AccountDeletionRequestModel | None:
        condition = (
            AccountDeletionRequestModel.customer_id == actor_id
            if actor_type == "customer"
            else AccountDeletionRequestModel.performer_id == actor_id
        )
        result = await self._session.execute(
            select(AccountDeletionRequestModel).where(
                condition,
                AccountDeletionRequestModel.status.not_in(TERMINAL_STATUSES),
            )
        )
        return result.scalar_one_or_none()

    async def links_for_owner(
        self, *, entity_type: str, entity_id: UUID
    ) -> list[tuple[FileModel, FileLinkModel]]:
        result = await self._session.execute(
            select(FileModel, FileLinkModel)
            .join(FileLinkModel, FileLinkModel.file_id == FileModel.id)
            .where(
                FileLinkModel.entity_type == entity_type,
                FileLinkModel.entity_id == entity_id,
                FileModel.status == "uploaded",
            )
            .order_by(FileLinkModel.sort_order, FileLinkModel.created_at),
        )
        return [(row[0], row[1]) for row in result.all()]

    async def list_records(
        self, *, model: type[Any], status: str | None, offset: int, limit: int
    ) -> tuple[list[Any], int]:
        conditions = [model.status == status] if status else []
        total = await self._session.scalar(
            select(func.count()).select_from(model).where(*conditions)
        )
        result = await self._session.execute(
            select(model)
            .where(*conditions)
            .order_by(model.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars()), int(total or 0)

    async def list_records_for_actor(
        self,
        *,
        model: type[Any],
        condition: Any,
        status: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Any], int]:
        conditions = [condition]
        if status is not None:
            conditions.append(model.status == status)
        total = await self._session.scalar(
            select(func.count()).select_from(model).where(*conditions),
        )
        result = await self._session.execute(
            select(model)
            .where(*conditions)
            .order_by(model.created_at.desc())
            .offset(offset)
            .limit(limit),
        )
        return list(result.scalars()), int(total or 0)

    async def get_record(self, *, model: type[Any], record_id: UUID) -> Any:
        record = await self._session.get(model, record_id)
        if record is None:
            raise NotFoundError("Support record not found")
        return record

    async def update_record(
        self,
        *,
        model: type[Any],
        record_id: UUID,
        status: str,
        admin_comment: str | None,
    ) -> Any:
        allowed_statuses = {"open", "closed"} if model is DisputeModel else STATUSES
        if status not in allowed_statuses:
            raise ValidationError("Invalid support status")
        record = await self.get_record(model=model, record_id=record_id)
        record.status = status
        record.admin_comment = admin_comment
        if isinstance(record, AccountDeletionRequestModel):
            record.resolved_at = utc_now() if status == "resolved" else None
        return record

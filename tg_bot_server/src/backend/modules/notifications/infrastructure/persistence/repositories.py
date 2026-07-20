from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import utc_now
from backend.modules.notifications.infrastructure.persistence.models import (
    NotificationModel,
)


class SqlAlchemyNotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, notification: NotificationModel) -> NotificationModel:
        self._session.add(notification)
        return notification

    async def list_admin_inbox(
        self,
        *,
        admin_id: UUID,
        status: str | None,
        is_read: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[NotificationModel], int]:
        conditions = [
            NotificationModel.recipient_type == "admin",
            NotificationModel.admin_id == admin_id,
        ]
        if status is not None:
            conditions.append(NotificationModel.status == status)
        if is_read is True:
            conditions.append(NotificationModel.read_at.is_not(None))
        elif is_read is False:
            conditions.append(NotificationModel.read_at.is_(None))
        total = await self._session.scalar(
            select(func.count()).select_from(NotificationModel).where(*conditions),
        )
        result = await self._session.execute(
            select(NotificationModel)
            .where(*conditions)
            .order_by(NotificationModel.created_at.desc())
            .offset(offset)
            .limit(limit),
        )
        return list(result.scalars()), int(total or 0)

    async def mark_admin_read(
        self,
        *,
        admin_id: UUID,
        notification_ids: list[UUID],
    ) -> int:
        conditions = (
            NotificationModel.id.in_(notification_ids),
            NotificationModel.admin_id == admin_id,
            NotificationModel.recipient_type == "admin",
            NotificationModel.read_at.is_(None),
        )
        count = await self._session.scalar(
            select(func.count()).select_from(NotificationModel).where(*conditions),
        )
        await self._session.execute(
            update(NotificationModel).where(*conditions).values(read_at=utc_now()),
        )
        return int(count or 0)

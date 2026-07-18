from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.notifications.infrastructure.persistence.models import (
    NotificationModel,
)


class SqlAlchemyNotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, notification: NotificationModel) -> NotificationModel:
        self._session.add(notification)
        return notification

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.admin.infrastructure.persistence.audit_models import (
    AdminAuditLogModel,
)


class SqlAlchemyAdminAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        admin_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: UUID | None,
        reason: str | None = None,
        audit_metadata: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            AdminAuditLogModel(
                admin_id=admin_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                reason=reason,
                audit_metadata=audit_metadata or {},
            ),
        )

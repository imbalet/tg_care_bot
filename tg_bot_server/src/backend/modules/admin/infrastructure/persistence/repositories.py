from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import utc_now
from backend.modules.admin.domain import Admin, AdminStatus
from backend.modules.admin.infrastructure.persistence.models import AdminModel


def _to_domain(model: AdminModel) -> Admin:
    return Admin(
        id=model.id,
        email=model.email,
        full_name=model.full_name,
        password_hash=model.password_hash,
        status=AdminStatus(model.status),
        last_login_at=model.last_login_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyAdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, admin_id: UUID) -> Admin | None:
        model = await self._session.get(AdminModel, admin_id)
        if model is None:
            return None
        return _to_domain(model)

    async def get_by_email(self, email: str) -> Admin | None:
        result = await self._session.execute(
            select(AdminModel).where(AdminModel.email == email.lower()),
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _to_domain(model)

    async def add(self, admin: Admin) -> None:
        self._session.add(
            AdminModel(
                id=admin.id,
                email=admin.email,
                full_name=admin.full_name,
                password_hash=admin.password_hash,
                status=admin.status.value,
                last_login_at=admin.last_login_at,
                created_at=admin.created_at,
                updated_at=admin.updated_at,
            ),
        )

    async def update_last_login(self, admin: Admin) -> None:
        model = await self._session.get(AdminModel, admin.id)
        if model is None:
            return
        now = utc_now()
        model.last_login_at = now
        model.updated_at = now
        admin.last_login_at = now
        admin.updated_at = now

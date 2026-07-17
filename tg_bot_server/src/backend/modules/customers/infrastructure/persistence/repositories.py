from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import new_uuid, utc_now
from backend.modules.catalog.infrastructure import CityModel, LegalDocumentModel
from backend.modules.customers.domain import ContactMethod, Customer, CustomerStatus
from backend.modules.customers.infrastructure.persistence.models import (
    CustomerModel,
    LegalAcceptanceModel,
)


def _to_domain(model: CustomerModel) -> Customer:
    return Customer(
        id=model.id,
        telegram_id=model.telegram_id,
        full_name=model.full_name,
        phone=model.phone,
        telegram_username=model.telegram_username,
        contact_method=ContactMethod(model.contact_method),
        city_id=model.city_id,
        status=CustomerStatus(model.status),
        blocked_reason=model.blocked_reason,
        deleted_at=model.deleted_at,
        anonymized_at=model.anonymized_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyCustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: int) -> Customer | None:
        result = await self._session.execute(
            select(CustomerModel).where(CustomerModel.telegram_id == telegram_id),
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _to_domain(model)

    async def get_city_is_active(self, city_id: UUID) -> bool:
        result = await self._session.execute(
            select(CityModel.is_active).where(CityModel.id == city_id),
        )
        return result.scalar_one_or_none() is True

    async def list_active_legal_document_ids(self) -> tuple[UUID, ...]:
        result = await self._session.execute(
            select(LegalDocumentModel.id).where(LegalDocumentModel.is_active.is_(True)),
        )
        return tuple(result.scalars())

    async def add(self, customer: Customer) -> None:
        self._session.add(
            CustomerModel(
                id=customer.id,
                telegram_id=customer.telegram_id,
                full_name=customer.full_name,
                phone=customer.phone,
                telegram_username=customer.telegram_username,
                contact_method=customer.contact_method.value,
                city_id=customer.city_id,
                status=customer.status.value,
                blocked_reason=customer.blocked_reason,
                deleted_at=customer.deleted_at,
                anonymized_at=customer.anonymized_at,
                created_at=customer.created_at,
                updated_at=customer.updated_at,
            ),
        )
        await self._session.flush()

    async def add_legal_acceptances(
        self,
        *,
        customer_id: UUID,
        document_ids: tuple[UUID, ...],
    ) -> None:
        now = utc_now()
        existing_result = await self._session.execute(
            select(LegalAcceptanceModel.document_id).where(
                LegalAcceptanceModel.customer_id == customer_id,
                LegalAcceptanceModel.revoked_at.is_(None),
            ),
        )
        existing_ids = set(existing_result.scalars())
        for document_id in document_ids:
            if document_id in existing_ids:
                continue
            self._session.add(
                LegalAcceptanceModel(
                    id=new_uuid(),
                    account_type="customer",
                    customer_id=customer_id,
                    performer_id=None,
                    document_id=document_id,
                    accepted_at=now,
                    revoked_at=None,
                    created_at=now,
                ),
            )

    async def update(self, customer: Customer) -> None:
        model = await self._session.get(CustomerModel, customer.id)
        if model is None:
            return
        model.full_name = customer.full_name
        model.phone = customer.phone
        model.telegram_username = customer.telegram_username
        model.contact_method = customer.contact_method.value
        model.city_id = customer.city_id
        model.status = customer.status.value
        model.blocked_reason = customer.blocked_reason
        model.deleted_at = customer.deleted_at
        model.anonymized_at = customer.anonymized_at
        model.updated_at = customer.updated_at

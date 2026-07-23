from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.common.domain import ValidationError
from backend.modules.customers.application.use_cases import (
    RegisterCustomerCommand,
    RegisterCustomerUseCase,
)
from backend.modules.customers.domain import ContactMethod
from tests.support.fakes import FakeClock


@pytest.mark.unit
async def test_customer_registration_requires_all_active_legal_documents() -> None:
    repository = AsyncMock()
    city_id = uuid4()
    repository.get_city_is_active.return_value = True
    repository.list_active_legal_document_ids.return_value = (uuid4(), uuid4())

    with pytest.raises(ValidationError, match="legal documents"):
        await RegisterCustomerUseCase(repository).execute(
            RegisterCustomerCommand(
                telegram_id=100,
                full_name="Test Customer",
                phone="+79990000000",
                city_id=city_id,
                contact_method="telegram",
                telegram_username="customer",
                accepted_legal_document_ids=(uuid4(),),
            ),
        )

    repository.add.assert_not_awaited()


@pytest.mark.unit
async def test_customer_registration_is_idempotent_for_existing_customer() -> None:
    repository = AsyncMock()
    city_id = uuid4()
    legal_id = uuid4()
    existing = type(
        "ExistingCustomer",
        (),
        {
            "id": uuid4(),
            "telegram_id": 100,
            "full_name": "Old Name",
            "phone": "+70000000000",
            "telegram_username": None,
            "contact_method": ContactMethod.TELEGRAM,
            "city_id": city_id,
            "status": type("Status", (), {"value": "active"})(),
            "updated_at": None,
        },
    )()
    repository.get_city_is_active.return_value = True
    repository.list_active_legal_document_ids.return_value = (legal_id,)
    repository.get_by_telegram_id.return_value = existing

    result = await RegisterCustomerUseCase(
        repository,
        FakeClock(datetime(2026, 1, 1, tzinfo=UTC)),
    ).execute(
        RegisterCustomerCommand(
            telegram_id=100,
            full_name="New Name",
            phone="+79990000000",
            city_id=city_id,
            contact_method="telegram",
            telegram_username="customer",
            accepted_legal_document_ids=(legal_id,),
        ),
    )

    assert result.full_name == "New Name"
    repository.add.assert_not_awaited()
    repository.update.assert_awaited_once_with(existing)

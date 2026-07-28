from typing import Any

import httpx
import pytest


@pytest.mark.e2e
async def test_customer_registration_repeat_updates_one_existing_account(
    e2e_client: httpx.AsyncClient,
    e2e_catalog: Any,
    e2e_db: Any,
    customer_factory: Any,
) -> None:
    customer = await customer_factory()
    registration_payload = {
        "telegram_id": customer.telegram_id,
        "full_name": "E2E Updated Customer",
        "phone": "+79990000001",
        "city_id": customer.city_id,
        "contact_method": "telegram",
        "telegram_username": f"updated_customer_{customer.telegram_id}",
        "accepted_legal_document_ids": e2e_catalog["legal_document_ids"],
    }

    first_repeat = await e2e_client.post(
        "/api/customers/register",
        json=registration_payload,
    )
    assert first_repeat.status_code == 201, first_repeat.text

    second_repeat = await e2e_client.post(
        "/api/customers/register",
        json=registration_payload,
    )
    assert second_repeat.status_code == 201, second_repeat.text
    assert second_repeat.json()["id"] == first_repeat.json()["id"] == customer.entity_id

    row = await e2e_db.fetchrow(
        "SELECT full_name, phone, telegram_username FROM customers WHERE id = $1",
        customer.entity_id,
    )
    assert row is not None
    assert dict(row) == {
        "full_name": "E2E Updated Customer",
        "phone": "+79990000001",
        "telegram_username": f"updated_customer_{customer.telegram_id}",
    }
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM customers WHERE telegram_id = $1",
            customer.telegram_id,
        )
        == 1
    )

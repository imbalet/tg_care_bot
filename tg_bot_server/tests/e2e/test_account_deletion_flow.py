from typing import Any

import httpx
import pytest


@pytest.mark.e2e
async def test_active_customer_order_blocks_account_deletion(
    e2e_client: httpx.AsyncClient,
    pool_order_factory: Any,
) -> None:
    customer, order = await pool_order_factory()

    preflight_response = await e2e_client.get(
        f"/api/customers/by-telegram/{customer.telegram_id}/deletion-preflight"
    )
    assert preflight_response.status_code == 200, preflight_response.text
    preflight = preflight_response.json()
    assert preflight["can_delete"] is False
    assert any(
        blocker["kind"] == "order" and blocker["id"] == order["id"]
        for blocker in preflight["blockers"]
    )

    deletion_response = await e2e_client.post(
        f"/api/customers/by-telegram/{customer.telegram_id}/deletion-requests"
    )
    assert deletion_response.status_code == 409, deletion_response.text
    assert "cannot be deleted" in deletion_response.json()["error"]["message"]


@pytest.mark.e2e
async def test_clean_customer_deletion_request_is_idempotent(
    e2e_client: httpx.AsyncClient,
    e2e_db: Any,
    customer_factory: Any,
) -> None:
    customer = await customer_factory()

    preflight_response = await e2e_client.get(
        f"/api/customers/by-telegram/{customer.telegram_id}/deletion-preflight"
    )
    assert preflight_response.status_code == 200, preflight_response.text
    assert preflight_response.json() == {"can_delete": True, "blockers": []}

    first_response = await e2e_client.post(
        f"/api/customers/by-telegram/{customer.telegram_id}/deletion-requests"
    )
    assert first_response.status_code == 201, first_response.text
    first = first_response.json()
    assert first["kind"] == "deletion"
    assert first["status"] == "open"

    second_response = await e2e_client.post(
        f"/api/customers/by-telegram/{customer.telegram_id}/deletion-requests"
    )
    assert second_response.status_code == 201, second_response.text
    assert second_response.json() == first

    account = await e2e_db.fetchrow(
        "SELECT status FROM customers WHERE id = $1",
        customer.entity_id,
    )
    assert account is not None
    assert account["status"] == "deletion_pending"
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM account_deletion_requests WHERE customer_id = $1",
            customer.entity_id,
        )
        == 1
    )

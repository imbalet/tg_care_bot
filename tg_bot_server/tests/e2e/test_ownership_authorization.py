from typing import Any

import httpx
import pytest


@pytest.mark.e2e
async def test_customer_cannot_read_or_change_another_customer_order(
    e2e_client: httpx.AsyncClient,
    direct_order_factory,
    customer_factory,
) -> None:
    owner, _performer, order = await direct_order_factory()
    other_customer = await customer_factory()

    read_response = await e2e_client.get(
        f"/api/orders/customer/{other_customer.entity_id}/my/{order['id']}"
    )
    assert read_response.status_code == 404, read_response.text

    list_response = await e2e_client.get(
        f"/api/orders/customer/{other_customer.entity_id}/my"
    )
    assert list_response.status_code == 200, list_response.text
    assert all(item["id"] != order["id"] for item in list_response.json()["items"])

    publish_response = await e2e_client.post(
        f"/api/orders/{order['id']}/publish-pool",
        json={"customer_id": other_customer.entity_id},
    )
    assert publish_response.status_code == 404, publish_response.text

    owner_read_response = await e2e_client.get(
        f"/api/orders/customer/{owner.entity_id}/my/{order['id']}"
    )
    assert owner_read_response.status_code == 200, owner_read_response.text


@pytest.mark.e2e
async def test_performer_cannot_read_or_execute_another_performers_order(
    e2e_client: httpx.AsyncClient,
    e2e_db: Any,
    direct_order_factory,
    performer_factory,
) -> None:
    _customer, _owner, order = await direct_order_factory()
    other_performer = await performer_factory()

    read_response = await e2e_client.get(
        f"/api/orders/performer/{other_performer.entity_id}/my/{order['id']}"
    )
    assert read_response.status_code == 404, read_response.text

    start_response = await e2e_client.post(
        f"/api/orders/{order['id']}/start",
        json={"performer_id": other_performer.entity_id},
    )
    assert start_response.status_code == 404, start_response.text

    order_state = await e2e_db.fetchrow(
        "SELECT status, selected_performer_id FROM orders WHERE id = $1",
        order["id"],
    )
    assert order_state is not None
    assert order_state["status"] == "searching"
    assert order_state["selected_performer_id"] is None


@pytest.mark.e2e
async def test_service_key_cannot_access_admin_session_endpoints(
    e2e_client: httpx.AsyncClient,
) -> None:
    response = await e2e_client.get("/admin/me")

    assert response.status_code in {401, 403}, response.text

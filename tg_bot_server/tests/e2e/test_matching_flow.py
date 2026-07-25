import httpx
import pytest


@pytest.mark.e2e
async def test_performer_can_respond_and_customer_can_select_pool_order(
    e2e_client: httpx.AsyncClient,
    performer_factory,
    pool_order_factory,
) -> None:
    customer, order = await pool_order_factory()
    performer = await performer_factory()

    available_response = await e2e_client.get(
        "/api/orders/available",
        params={"performer_id": performer.entity_id},
    )
    assert available_response.status_code == 200, available_response.text
    assert any(item["id"] == order["id"] for item in available_response.json())

    response_response = await e2e_client.post(
        f"/api/orders/{order['id']}/pool-responses",
        json={"performer_id": performer.entity_id},
    )
    assert response_response.status_code == 201, response_response.text
    match = response_response.json()
    assert match["status"] == "active"

    matches_response = await e2e_client.get(
        f"/api/orders/{order['id']}/matches",
        params={"customer_id": customer.entity_id},
    )
    assert matches_response.status_code == 200, matches_response.text
    assert matches_response.json()[0]["id"] == match["id"]

    select_response = await e2e_client.post(
        f"/api/orders/matches/{match['id']}/pool/select",
        json={"customer_id": customer.entity_id},
    )
    assert select_response.status_code == 200, select_response.text
    assert select_response.json()["match"]["status"] == "selected"
    assert select_response.json()["order"]["status"] == "waiting_payment"

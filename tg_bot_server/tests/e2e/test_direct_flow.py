import httpx
import pytest


@pytest.mark.e2e
async def test_direct_invitation_can_be_accepted_and_wait_for_payment(
    e2e_client: httpx.AsyncClient,
    direct_order_factory,
) -> None:
    customer, performer, order = await direct_order_factory()

    matches_response = await e2e_client.get(
        f"/api/orders/{order['id']}/matches",
        params={"customer_id": customer.entity_id},
    )
    assert matches_response.status_code == 200, matches_response.text
    assert len(matches_response.json()) == 1
    match = matches_response.json()[0]
    assert match["source"] == "direct"
    assert match["status"] == "pending"

    accept_response = await e2e_client.post(
        f"/api/orders/matches/{match['id']}/direct/accept",
        json={"performer_id": performer.entity_id},
    )
    assert accept_response.status_code == 200, accept_response.text
    payload = accept_response.json()
    assert payload["match"]["status"] == "selected"
    assert payload["order"]["status"] == "waiting_payment"
    assert payload["payment"]["confirmation_url"]

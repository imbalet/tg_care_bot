import json
from typing import Any

import httpx
import pytest


@pytest.mark.e2e
async def test_direct_invitation_can_be_accepted_and_wait_for_payment(
    e2e_client: httpx.AsyncClient,
    direct_order_factory: Any,
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


@pytest.mark.e2e
async def test_direct_invitation_notification_uses_match_id(
    e2e_client: httpx.AsyncClient,
    e2e_db: Any,
    direct_order_factory: Any,
    performer_factory: Any,
) -> None:
    customer, performer, order = await direct_order_factory()
    second_performer = await performer_factory()

    matches_response = await e2e_client.get(
        f"/api/orders/{order['id']}/matches",
        params={"customer_id": customer.entity_id},
    )
    assert matches_response.status_code == 200, matches_response.text
    initial_match = matches_response.json()[0]

    reject_response = await e2e_client.post(
        f"/api/orders/matches/{initial_match['id']}/direct/reject",
        json={"performer_id": performer.entity_id},
    )
    assert reject_response.status_code == 200, reject_response.text

    invite_response = await e2e_client.post(
        f"/api/orders/{order['id']}/direct/performer",
        json={
            "customer_id": customer.entity_id,
            "performer_id": second_performer.entity_id,
        },
    )
    assert invite_response.status_code == 201, invite_response.text
    invited_match = invite_response.json()

    notification = await e2e_db.fetchrow(
        """
        SELECT entity_id, payload, deduplication_key
        FROM notifications
        WHERE type = 'direct_invitation_created'
          AND entity_id = $1
        """,
        invited_match["id"],
    )
    assert notification is not None
    assert str(notification["entity_id"]) == invited_match["id"]
    payload = notification["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert payload["match_id"] == invited_match["id"]
    assert notification["deduplication_key"] == (
        f"direct-invitation-created:{invited_match['id']}"
    )

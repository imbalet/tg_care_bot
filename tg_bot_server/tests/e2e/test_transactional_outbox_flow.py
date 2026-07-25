import httpx
import pytest


@pytest.mark.e2e
async def test_rejected_repeat_command_does_not_create_extra_outbox_task(
    e2e_client: httpx.AsyncClient,
    e2e_db,
    performer_factory,
    pool_order_factory,
) -> None:
    _customer, order = await pool_order_factory()
    performer = await performer_factory()
    payload = {"performer_id": performer.entity_id}

    first_response = await e2e_client.post(
        f"/api/orders/{order['id']}/pool-responses",
        json=payload,
    )
    assert first_response.status_code == 201, first_response.text
    match_id = first_response.json()["id"]

    before = await e2e_db.fetchrow(
        """
        SELECT
            (SELECT count(*) FROM order_matches WHERE order_id = $1) AS matches,
            (SELECT count(*) FROM notifications WHERE entity_id = $2) AS notifications
        """,
        order["id"],
        match_id,
    )
    assert before is not None
    assert dict(before) == {"matches": 1, "notifications": 1}

    repeat_response = await e2e_client.post(
        f"/api/orders/{order['id']}/pool-responses",
        json=payload,
    )
    assert repeat_response.status_code == 409, repeat_response.text

    after = await e2e_db.fetchrow(
        """
        SELECT
            (SELECT count(*) FROM order_matches WHERE order_id = $1) AS matches,
            (SELECT count(*) FROM notifications WHERE entity_id = $2) AS notifications
        """,
        order["id"],
        match_id,
    )
    assert after is not None
    assert dict(after) == dict(before)

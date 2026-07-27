from __future__ import annotations

import asyncio
from typing import Any

import asyncpg
import httpx
import pytest


async def _create_direct_order_for_existing_performer(
    e2e_client: httpx.AsyncClient,
    customer: Any,
    performer: Any,
    template_order: dict[str, Any],
    service_id: str,
) -> dict[str, Any]:
    care_object_response = await e2e_client.post(
        f"/api/customers/by-telegram/{customer.telegram_id}/care-objects",
        json={
            "object_type": "pet",
            "display_name": "E2E Concurrent Pet",
            "age_group": "adult",
            "species": "dog",
            "pet_size": "medium",
        },
    )
    assert care_object_response.status_code == 201, care_object_response.text

    order_response = await e2e_client.post(
        "/api/orders/direct",
        json={
            "customer_id": customer.entity_id,
            "performer_id": performer.entity_id,
            "service_id": service_id,
            "start_at": template_order["start_at"],
            "end_at": template_order["end_at"],
            "care_object_ids": [care_object_response.json()["id"]],
            "location_source": "performer_address",
            "address_id": None,
            "report_photo_consent": None,
            "option_values": {},
        },
    )
    assert order_response.status_code == 201, order_response.text
    return order_response.json()


@pytest.mark.e2e
async def test_concurrent_direct_accept_has_single_winner(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    customer_factory,
    direct_order_factory,
) -> None:
    first_customer, performer, first_order = await direct_order_factory()
    second_customer = await customer_factory()
    second_order = await _create_direct_order_for_existing_performer(
        e2e_client,
        second_customer,
        performer,
        first_order,
        first_order["service_id"],
    )

    first_matches_response = await e2e_client.get(
        f"/api/orders/{first_order['id']}/matches",
        params={"customer_id": first_customer.entity_id},
    )
    second_matches_response = await e2e_client.get(
        f"/api/orders/{second_order['id']}/matches",
        params={"customer_id": second_customer.entity_id},
    )
    assert first_matches_response.status_code == 200, first_matches_response.text
    assert second_matches_response.status_code == 200, second_matches_response.text
    first_match = first_matches_response.json()[0]
    second_match = second_matches_response.json()[0]

    start_event = asyncio.Event()

    async def accept(match_id: str) -> httpx.Response:
        await start_event.wait()
        return await e2e_client.post(
            f"/api/orders/matches/{match_id}/direct/accept",
            json={"performer_id": performer.entity_id},
        )

    first_task = asyncio.create_task(accept(first_match["id"]))
    second_task = asyncio.create_task(accept(second_match["id"]))
    start_event.set()
    first_response, second_response = await asyncio.gather(first_task, second_task)

    assert sorted((first_response.status_code, second_response.status_code)) == [
        200,
        409,
    ]
    successful_order_id = (
        first_order["id"] if first_response.status_code == 200 else second_order["id"]
    )
    rejected_order_id = (
        second_order["id"] if first_response.status_code == 200 else first_order["id"]
    )

    order_rows = await e2e_db.fetch(
        """
        SELECT id, status, selected_performer_id, selected_match_id,
               active_payment_id
        FROM orders
        WHERE id = ANY($1::uuid[])
        ORDER BY id
        """,
        [first_order["id"], second_order["id"]],
    )
    assert sum(row["status"] == "waiting_payment" for row in order_rows) == 1
    winner = next(row for row in order_rows if str(row["id"]) == successful_order_id)
    loser = next(row for row in order_rows if str(row["id"]) == rejected_order_id)
    assert winner["status"] == "waiting_payment"
    assert str(winner["selected_performer_id"]) == performer.entity_id
    assert winner["selected_match_id"] is not None
    assert winner["active_payment_id"] is not None
    assert loser["status"] == "searching"
    assert loser["selected_performer_id"] is None
    assert loser["selected_match_id"] is None
    assert loser["active_payment_id"] is None

    match_rows = await e2e_db.fetch(
        """
        SELECT order_id, status
        FROM order_matches
        WHERE id = ANY($1::uuid[])
        ORDER BY id
        """,
        [first_match["id"], second_match["id"]],
    )
    assert sorted(
        (str(row["order_id"]), row["status"]) for row in match_rows
    ) == sorted(
        [(successful_order_id, "selected"), (rejected_order_id, "pending")],
    )
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM payments WHERE order_id = $1",
            successful_order_id,
        )
        == 1
    )
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM payments WHERE order_id = $1",
            rejected_order_id,
        )
        == 0
    )


@pytest.mark.e2e
async def test_repeated_direct_accept_is_rejected_without_side_effects(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
) -> None:
    customer, performer, order = await direct_order_factory()
    matches_response = await e2e_client.get(
        f"/api/orders/{order['id']}/matches",
        params={"customer_id": customer.entity_id},
    )
    assert matches_response.status_code == 200, matches_response.text
    match = matches_response.json()[0]

    initial_accept = await e2e_client.post(
        f"/api/orders/matches/{match['id']}/direct/accept",
        json={"performer_id": performer.entity_id},
    )
    assert initial_accept.status_code == 200, initial_accept.text

    repeated_accept = await e2e_client.post(
        f"/api/orders/matches/{match['id']}/direct/accept",
        json={"performer_id": performer.entity_id},
    )
    assert repeated_accept.status_code == 409, repeated_accept.text
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM payments WHERE order_id = $1",
            order["id"],
        )
        == 1
    )
    assert (
        await e2e_db.fetchval(
            """
            SELECT count(*) FROM notifications
            WHERE entity_id = $1 AND type IN ('direct_accepted', 'payment_created')
            """,
            match["id"],
        )
        == 2
    )


@pytest.mark.e2e
async def test_direct_accept_after_rejection_is_rejected_without_payment(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
) -> None:
    customer, performer, order = await direct_order_factory()
    matches_response = await e2e_client.get(
        f"/api/orders/{order['id']}/matches",
        params={"customer_id": customer.entity_id},
    )
    assert matches_response.status_code == 200, matches_response.text
    match = matches_response.json()[0]

    reject_response = await e2e_client.post(
        f"/api/orders/matches/{match['id']}/direct/reject",
        json={"performer_id": performer.entity_id},
    )
    assert reject_response.status_code == 200, reject_response.text

    accept_response = await e2e_client.post(
        f"/api/orders/matches/{match['id']}/direct/accept",
        json={"performer_id": performer.entity_id},
    )
    assert accept_response.status_code == 409, accept_response.text
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM payments WHERE order_id = $1",
            order["id"],
        )
        == 0
    )
    assert (
        await e2e_db.fetchval(
            "SELECT status FROM order_matches WHERE id = $1",
            match["id"],
        )
        == "rejected"
    )


@pytest.mark.e2e
async def test_direct_accept_after_expiration_is_rejected_without_payment(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
) -> None:
    customer, performer, order = await direct_order_factory()
    matches_response = await e2e_client.get(
        f"/api/orders/{order['id']}/matches",
        params={"customer_id": customer.entity_id},
    )
    assert matches_response.status_code == 200, matches_response.text
    match = matches_response.json()[0]
    await e2e_db.execute(
        """
        UPDATE order_matches
        SET response_expires_at = now() - interval '1 second'
        WHERE id = $1
        """,
        match["id"],
    )

    accept_response = await e2e_client.post(
        f"/api/orders/matches/{match['id']}/direct/accept",
        json={"performer_id": performer.entity_id},
    )
    assert accept_response.status_code == 409, accept_response.text
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM payments WHERE order_id = $1",
            order["id"],
        )
        == 0
    )
    assert (
        await e2e_db.fetchval(
            "SELECT status FROM order_matches WHERE id = $1",
            match["id"],
        )
        == "pending"
    )

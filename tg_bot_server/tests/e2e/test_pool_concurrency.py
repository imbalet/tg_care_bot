from __future__ import annotations

import asyncio

import asyncpg
import httpx
import pytest


async def _create_pool_response(
    e2e_client: httpx.AsyncClient,
    order_id: str,
    performer_id: str,
    start_event: asyncio.Event,
) -> httpx.Response:
    await start_event.wait()
    return await e2e_client.post(
        f"/api/orders/{order_id}/pool-responses",
        json={"performer_id": performer_id},
    )


async def _select_pool_match(
    e2e_client: httpx.AsyncClient,
    match_id: str,
    customer_id: str,
    start_event: asyncio.Event,
) -> httpx.Response:
    await start_event.wait()
    return await e2e_client.post(
        f"/api/orders/matches/{match_id}/pool/select",
        json={"customer_id": customer_id},
    )


@pytest.mark.e2e
async def test_concurrent_pool_responses_and_selection_have_single_winner(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    performer_factory,
    pool_order_factory,
) -> None:
    customer, order = await pool_order_factory()
    first_performer = await performer_factory()
    second_performer = await performer_factory()
    response_start = asyncio.Event()

    first_response_task = asyncio.create_task(
        _create_pool_response(
            e2e_client,
            order["id"],
            first_performer.entity_id,
            response_start,
        ),
    )
    second_response_task = asyncio.create_task(
        _create_pool_response(
            e2e_client,
            order["id"],
            second_performer.entity_id,
            response_start,
        ),
    )
    response_start.set()
    first_response, second_response = await asyncio.gather(
        first_response_task,
        second_response_task,
    )
    assert first_response.status_code == 201, first_response.text
    assert second_response.status_code == 201, second_response.text
    first_match = first_response.json()
    second_match = second_response.json()

    select_start = asyncio.Event()
    first_select_task = asyncio.create_task(
        _select_pool_match(
            e2e_client,
            first_match["id"],
            customer.entity_id,
            select_start,
        ),
    )
    second_select_task = asyncio.create_task(
        _select_pool_match(
            e2e_client,
            second_match["id"],
            customer.entity_id,
            select_start,
        ),
    )
    select_start.set()
    first_select, second_select = await asyncio.gather(
        first_select_task,
        second_select_task,
    )
    assert sorted((first_select.status_code, second_select.status_code)) == [
        200,
        409,
    ]

    winner_match_id = (
        first_match["id"] if first_select.status_code == 200 else second_match["id"]
    )
    loser_match_id = (
        second_match["id"] if first_select.status_code == 200 else first_match["id"]
    )
    order_row = await e2e_db.fetchrow(
        """
        SELECT status, selected_match_id, active_payment_id
        FROM orders
        WHERE id = $1
        """,
        order["id"],
    )
    assert order_row is not None
    assert order_row["status"] == "waiting_payment"
    assert str(order_row["selected_match_id"]) == winner_match_id
    assert order_row["active_payment_id"] is not None
    assert (
        await e2e_db.fetchval(
            "SELECT status FROM order_matches WHERE id = $1",
            loser_match_id,
        )
        == "rejected"
    )
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM payments WHERE order_id = $1",
            order["id"],
        )
        == 1
    )
    stale_select = await e2e_client.post(
        f"/api/orders/matches/{loser_match_id}/pool/select",
        json={"customer_id": customer.entity_id},
    )
    assert stale_select.status_code == 409, stale_select.text
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM payments WHERE order_id = $1",
            order["id"],
        )
        == 1
    )
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM notifications WHERE entity_id = $1",
            winner_match_id,
        )
        == 3
    )

    repeated_select = await e2e_client.post(
        f"/api/orders/matches/{winner_match_id}/pool/select",
        json={"customer_id": customer.entity_id},
    )
    assert repeated_select.status_code == 409, repeated_select.text
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM payments WHERE order_id = $1",
            order["id"],
        )
        == 1
    )


@pytest.mark.e2e
async def test_pool_response_limit_rejects_sixth_response(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    performer_factory,
    pool_order_factory,
) -> None:
    customer, order = await pool_order_factory()
    performers = [await performer_factory() for _ in range(6)]
    start_event = asyncio.Event()
    tasks = [
        asyncio.create_task(
            _create_pool_response(
                e2e_client,
                order["id"],
                performer.entity_id,
                start_event,
            ),
        )
        for performer in performers
    ]
    start_event.set()
    responses = await asyncio.gather(*tasks)

    assert sorted(response.status_code for response in responses) == [
        201,
        201,
        201,
        201,
        201,
        409,
    ]
    assert (
        await e2e_db.fetchval(
            """
            SELECT count(*) FROM order_matches
            WHERE order_id = $1 AND status = 'active'
            """,
            order["id"],
        )
        == 5
    )
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM payments WHERE order_id = $1",
            order["id"],
        )
        == 0
    )

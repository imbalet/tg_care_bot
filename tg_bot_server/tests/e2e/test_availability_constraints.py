from __future__ import annotations

from typing import Any

import asyncpg
import httpx
import pytest


def _suitable_params(
    customer: Any,
    order: dict[str, Any],
) -> dict[str, object]:
    return {
        "city_id": customer.city_id,
        "service_id": order["service_id"],
        "starts_at": order["start_at"],
        "ends_at": order["end_at"],
        "objects_count": 1,
    }


@pytest.mark.e2e
async def test_suitable_performers_excludes_disabled_service_and_non_accepting(
    e2e_client: httpx.AsyncClient,
    performer_factory,
    pool_order_factory,
) -> None:
    customer, order = await pool_order_factory()
    performer = await performer_factory()
    params = _suitable_params(customer, order)

    initial_response = await e2e_client.get(
        "/api/availability/suitable-performers",
        params=params,
    )
    assert initial_response.status_code == 200, initial_response.text
    assert performer.entity_id in {
        item["performer_id"] for item in initial_response.json()
    }

    disabled_response = await e2e_client.patch(
        f"/api/performers/by-telegram/{performer.telegram_id}/services/"
        f"{order['service_id']}/enabled",
        json={"is_enabled": False},
    )
    assert disabled_response.status_code == 200, disabled_response.text
    disabled_suitable = await e2e_client.get(
        "/api/availability/suitable-performers",
        params=params,
    )
    assert disabled_suitable.status_code == 200, disabled_suitable.text
    assert performer.entity_id not in {
        item["performer_id"] for item in disabled_suitable.json()
    }

    enabled_response = await e2e_client.patch(
        f"/api/performers/by-telegram/{performer.telegram_id}/services/"
        f"{order['service_id']}/enabled",
        json={"is_enabled": True},
    )
    assert enabled_response.status_code == 200, enabled_response.text
    accepting_response = await e2e_client.patch(
        f"/api/performers/by-telegram/{performer.telegram_id}/accepting-orders",
        json={"is_accepting_orders": False},
    )
    assert accepting_response.status_code == 200, accepting_response.text
    not_accepting_suitable = await e2e_client.get(
        "/api/availability/suitable-performers",
        params=params,
    )
    assert not_accepting_suitable.status_code == 200, not_accepting_suitable.text
    assert performer.entity_id not in {
        item["performer_id"] for item in not_accepting_suitable.json()
    }


@pytest.mark.e2e
async def test_suitable_performers_excludes_missing_address_and_inactive_performer(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    performer_factory,
    pool_order_factory,
) -> None:
    customer, order = await pool_order_factory()
    missing_address = await performer_factory()
    inactive = await performer_factory()
    params = _suitable_params(customer, order)

    await e2e_db.execute(
        "UPDATE performers SET current_address_id = NULL WHERE id = $1",
        missing_address.entity_id,
    )
    await e2e_db.execute(
        "UPDATE performers SET status = 'profile_pending' WHERE id = $1",
        inactive.entity_id,
    )

    suitable_response = await e2e_client.get(
        "/api/availability/suitable-performers",
        params=params,
    )
    assert suitable_response.status_code == 200, suitable_response.text
    suitable_ids = {item["performer_id"] for item in suitable_response.json()}
    assert missing_address.entity_id not in suitable_ids
    assert inactive.entity_id not in suitable_ids


@pytest.mark.e2e
async def test_unavailable_override_and_selected_order_block_pool_response(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
    pool_order_factory,
    performer_factory,
) -> None:
    customer, order = await pool_order_factory()
    performer = await performer_factory()
    override_response = await e2e_client.post(
        f"/api/performers/by-telegram/{performer.telegram_id}/calendar-overrides",
        json={
            "override_type": "unavailable",
            "starts_at": order["start_at"],
            "ends_at": order["end_at"],
            "comment": "E2E unavailable interval",
        },
    )
    assert override_response.status_code == 201, override_response.text

    availability_response = await e2e_client.get(
        f"/api/availability/performers/{performer.entity_id}/check",
        params={
            "service_id": order["service_id"],
            "starts_at": order["start_at"],
            "ends_at": order["end_at"],
        },
    )
    assert availability_response.status_code == 200, availability_response.text
    assert availability_response.json() == {
        "performer_id": performer.entity_id,
        "is_available": False,
        "reasons": ["unavailable_override"],
    }
    blocked_response = await e2e_client.post(
        f"/api/orders/{order['id']}/pool-responses",
        json={"performer_id": performer.entity_id},
    )
    assert blocked_response.status_code == 409, blocked_response.text
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM order_matches WHERE order_id = $1",
            order["id"],
        )
        == 0
    )

    (
        confirmed_customer,
        confirmed_performer,
        confirmed_order,
    ) = await direct_order_factory()
    matches_response = await e2e_client.get(
        f"/api/orders/{confirmed_order['id']}/matches",
        params={"customer_id": confirmed_customer.entity_id},
    )
    assert matches_response.status_code == 200, matches_response.text
    accept_response = await e2e_client.post(
        f"/api/orders/matches/{matches_response.json()[0]['id']}/direct/accept",
        json={"performer_id": confirmed_performer.entity_id},
    )
    assert accept_response.status_code == 200, accept_response.text

    _, overlapping_order = await pool_order_factory()
    overlap_response = await e2e_client.post(
        f"/api/orders/{overlapping_order['id']}/pool-responses",
        json={"performer_id": confirmed_performer.entity_id},
    )
    assert overlap_response.status_code == 409, overlap_response.text
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM order_matches WHERE order_id = $1",
            overlapping_order["id"],
        )
        == 0
    )

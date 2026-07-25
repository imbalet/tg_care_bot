from __future__ import annotations

from typing import Any

import asyncpg
import httpx
import pytest


@pytest.mark.e2e
async def test_performer_address_change_does_not_change_order_snapshot(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
) -> None:
    customer, performer, order = await direct_order_factory()

    addresses_response = await e2e_client.get(
        f"/api/performers/by-telegram/{performer.telegram_id}/addresses",
    )
    assert addresses_response.status_code == 200, addresses_response.text
    initial_address = addresses_response.json()[0]

    matches_response = await e2e_client.get(
        f"/api/orders/{order['id']}/matches",
        params={"customer_id": customer.entity_id},
    )
    assert matches_response.status_code == 200, matches_response.text
    match = matches_response.json()[0]

    accept_response = await e2e_client.post(
        f"/api/orders/matches/{match['id']}/direct/accept",
        json={"performer_id": performer.entity_id},
    )
    assert accept_response.status_code == 200, accept_response.text
    assert accept_response.json()["order"]["status"] == "waiting_payment"

    snapshot = await e2e_db.fetchrow(
        """
        SELECT source_address_id, city_name, district_name, address_text,
               fias_id, latitude, longitude, entrance, floor, apartment, comment
        FROM order_address_snapshots
        WHERE order_id = $1
        """,
        order["id"],
    )
    assert snapshot is not None
    assert str(snapshot["source_address_id"]) == initial_address["id"]
    assert snapshot["address_text"] == initial_address["address_text"]
    assert snapshot["apartment"] is None
    assert snapshot["comment"] is None

    new_address_response = await e2e_client.post(
        f"/api/performers/by-telegram/{performer.telegram_id}/addresses",
        json={
            "city_id": performer.city_id,
            "unrestricted_value": "г. Москва, ул. Тестовая, д. 2",
            "apartment": "99",
            "comment": "Новый текущий адрес",
        },
    )
    assert new_address_response.status_code == 201, new_address_response.text
    new_address = new_address_response.json()
    assert new_address["id"] != initial_address["id"]

    current_address_response = await e2e_client.patch(
        f"/api/performers/by-telegram/{performer.telegram_id}/current-address/"
        f"{new_address['id']}",
    )
    assert current_address_response.status_code == 200, current_address_response.text
    assert current_address_response.json()["id"] == new_address["id"]

    updated_snapshot = await e2e_db.fetchrow(
        """
        SELECT source_address_id, city_name, district_name, address_text,
               fias_id, latitude, longitude, entrance, floor, apartment, comment
        FROM order_address_snapshots
        WHERE order_id = $1
        """,
        order["id"],
    )
    assert updated_snapshot == snapshot
    assert updated_snapshot["source_address_id"] != new_address["id"]
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM order_address_snapshots WHERE order_id = $1",
            order["id"],
        )
        == 1
    )

    customer_location_response = await e2e_client.get(
        f"/api/orders/customer/{customer.entity_id}/my/{order['id']}/location",
    )
    assert customer_location_response.status_code == 200, (
        customer_location_response.text
    )
    customer_location: dict[str, Any] = customer_location_response.json()
    assert customer_location["address"] is None
    assert customer_location["city_name"] == snapshot["city_name"]

    performer_location_response = await e2e_client.get(
        f"/api/orders/performer/{performer.entity_id}/my/{order['id']}/location",
    )
    assert performer_location_response.status_code == 200, (
        performer_location_response.text
    )
    assert performer_location_response.json()["address"] is None

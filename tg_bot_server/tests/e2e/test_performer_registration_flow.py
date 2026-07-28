from typing import Any

import httpx
import pytest


@pytest.mark.e2e
async def test_performer_can_be_registered_and_prepared_for_orders(
    e2e_client: httpx.AsyncClient,
    performer_factory: Any,
) -> None:
    performer = await performer_factory()

    response = await e2e_client.get(
        f"/api/performers/by-telegram/{performer.telegram_id}/registration-state",
    )

    assert response.status_code == 200, response.text
    assert response.json()["performer"]["id"] == performer.entity_id
    assert response.json()["performer"]["status"] == "active"

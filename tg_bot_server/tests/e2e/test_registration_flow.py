from __future__ import annotations

from typing import Any

import httpx
import pytest


@pytest.mark.e2e
async def test_customer_registration_fixture_creates_owned_profile(
    e2e_client: httpx.AsyncClient,
    customer_factory: Any,
) -> None:
    customer = await customer_factory()

    response = await e2e_client.get(
        f"/api/customers/by-telegram/{customer.telegram_id}/profile",
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == customer.entity_id
    assert response.json()["telegram_id"] == customer.telegram_id


@pytest.mark.e2e
async def test_customer_profile_is_not_accessible_without_service_key(
    test_settings: Any,
) -> None:
    async with httpx.AsyncClient(base_url=test_settings.e2e_base_url) as client:
        response = await client.get(
            "/api/customers/by-telegram/910000999/profile",
        )

    assert response.status_code == 401

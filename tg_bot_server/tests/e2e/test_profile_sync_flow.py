import httpx
import pytest


@pytest.mark.e2e
async def test_customer_and_performer_username_sync_persists_and_allows_removal(
    e2e_client: httpx.AsyncClient,
    e2e_db,
    customer_factory,
    performer_factory,
) -> None:
    customer = await customer_factory()
    performer = await performer_factory()

    customer_update = await e2e_client.patch(
        f"/api/customers/by-telegram/{customer.telegram_id}/telegram-username",
        json={"telegram_username": "customer_synced"},
    )
    assert customer_update.status_code == 200, customer_update.text
    assert customer_update.json()["telegram_username"] == "customer_synced"

    customer_remove = await e2e_client.patch(
        f"/api/customers/by-telegram/{customer.telegram_id}/telegram-username",
        json={"telegram_username": None},
    )
    assert customer_remove.status_code == 200, customer_remove.text
    assert customer_remove.json()["telegram_username"] is None

    performer_update = await e2e_client.patch(
        f"/api/performers/by-telegram/{performer.telegram_id}/telegram-username",
        json={"telegram_username": "performer_synced"},
    )
    assert performer_update.status_code == 200, performer_update.text
    assert performer_update.json()["telegram_username"] == "performer_synced"

    performer_remove = await e2e_client.patch(
        f"/api/performers/by-telegram/{performer.telegram_id}/telegram-username",
        json={"telegram_username": None},
    )
    assert performer_remove.status_code == 200, performer_remove.text
    assert performer_remove.json()["telegram_username"] is None

    rows = await e2e_db.fetchrow(
        """
        SELECT
            (
                SELECT telegram_username
                FROM customers
                WHERE id = $1
            ) AS customer_username,
            (
                SELECT telegram_username
                FROM performers
                WHERE id = $2
            ) AS performer_username
        """,
        customer.entity_id,
        performer.entity_id,
    )
    assert rows is not None
    assert dict(rows) == {"customer_username": None, "performer_username": None}

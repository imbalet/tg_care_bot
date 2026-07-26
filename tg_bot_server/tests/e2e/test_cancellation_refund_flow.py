from decimal import Decimal

import asyncpg
import httpx
import pytest

from tests.e2e.test_order_lifecycle_flow import _confirm_direct_order
from tests.support.settings import TestSettings


@pytest.mark.e2e
async def test_customer_can_cancel_before_payment_without_creating_refund(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
) -> None:
    customer, _performer, order = await direct_order_factory()

    preview_response = await e2e_client.get(
        f"/api/orders/customer/{customer.entity_id}/my/{order['id']}"
        "/cancellation-preview",
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert preview["can_cancel"] is True
    assert preview["refund_outcome"] == "none"
    assert Decimal(preview["refund_amount"]) == Decimal("0.00")

    cancel_response = await e2e_client.post(
        f"/api/orders/{order['id']}/cancel",
        json={"actor_type": "customer", "actor_id": customer.entity_id},
    )
    assert cancel_response.status_code == 200, cancel_response.text
    assert cancel_response.json()["status"] == "cancelled"

    repeated_response = await e2e_client.post(
        f"/api/orders/{order['id']}/cancel",
        json={"actor_type": "customer", "actor_id": customer.entity_id},
    )
    assert repeated_response.status_code == 409, repeated_response.text

    row = await e2e_db.fetchrow(
        """
        SELECT o.status,
               count(p.id) AS payment_count,
               count(r.id) AS refund_count
        FROM orders AS o
        LEFT JOIN payments AS p ON p.order_id = o.id
        LEFT JOIN refunds AS r ON r.order_id = o.id
        WHERE o.id = $1
        GROUP BY o.id, o.status
        """,
        order["id"],
    )
    assert row is not None
    assert dict(row) == {
        "status": "cancelled",
        "payment_count": 0,
        "refund_count": 0,
    }


@pytest.mark.e2e
async def test_customer_cancellation_after_payment_creates_idempotent_full_refund(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
    test_settings: TestSettings,
) -> None:
    customer, _performer, order = await _confirm_direct_order(
        direct_order_factory,
        e2e_client,
        e2e_db,
        test_settings,
    )

    preview_response = await e2e_client.get(
        f"/api/orders/customer/{customer['entity_id']}/my/{order['id']}"
        "/cancellation-preview",
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert preview["can_cancel"] is True
    assert preview["refund_outcome"] == "full"
    assert Decimal(preview["refund_amount"]) == Decimal(str(order["total_amount"]))

    cancel_response = await e2e_client.post(
        f"/api/orders/{order['id']}/cancel",
        json={"actor_type": "customer", "actor_id": customer["entity_id"]},
    )
    assert cancel_response.status_code == 200, cancel_response.text
    assert cancel_response.json()["status"] == "cancelled"

    repeated_response = await e2e_client.post(
        f"/api/orders/{order['id']}/cancel",
        json={"actor_type": "customer", "actor_id": customer["entity_id"]},
    )
    assert repeated_response.status_code == 409, repeated_response.text

    rows = await e2e_db.fetch(
        """
        SELECT p.status AS payment_status,
               r.status AS refund_status,
               r.refund_type,
               r.amount,
               r.reason,
               count(*) OVER () AS refund_count
        FROM payments AS p
        JOIN refunds AS r ON r.payment_id = p.id
        WHERE p.order_id = $1
        """,
        order["id"],
    )
    assert len(rows) == 1
    assert dict(rows[0]) == {
        "payment_status": "succeeded",
        "refund_status": "pending",
        "refund_type": "full",
        "amount": Decimal(str(order["total_amount"])),
        "reason": "customer_cancellation",
        "refund_count": 1,
    }

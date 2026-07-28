from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

import asyncpg
import httpx
import pytest

from tests.support.settings import TestSettings


def _sign_payload(payload: dict[str, Any], password: str) -> str:
    sign_data = {
        key: value
        for key, value in payload.items()
        if key != "Token" and not isinstance(value, (dict, list))
    }
    sign_data["Password"] = password
    raw = "".join(str(sign_data[key]) for key in sorted(sign_data))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _confirm_direct_order(
    direct_order_factory: Any,
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    test_settings: TestSettings,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    customer, performer, order = await direct_order_factory()
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
    payment = accept_response.json()["payment"]
    provider_payment_id = await e2e_db.fetchval(
        "SELECT provider_payment_id FROM payments WHERE id = $1",
        payment["payment_id"],
    )
    assert provider_payment_id

    payload: dict[str, Any] = {
        "TerminalKey": test_settings.tbank_terminal_key,
        "OrderId": payment["payment_id"],
        "Success": True,
        "Status": "CONFIRMED",
        "PaymentId": provider_payment_id,
        "Amount": int(Decimal(str(order["total_amount"])) * 100),
        "Date": datetime(2026, 1, 1, 10, tzinfo=UTC).isoformat(),
    }
    payload["Token"] = _sign_payload(payload, test_settings.tbank_password)
    webhook_response = await e2e_client.post(
        "/api/payments/webhooks/tbank",
        json=payload,
    )
    assert webhook_response.status_code == 200, webhook_response.text
    return customer.__dict__, performer.__dict__, order


async def _mock_requests(
    test_settings: TestSettings,
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(
        base_url=test_settings.telegram_api_base_url,
        timeout=test_settings.e2e_request_timeout_seconds,
    ) as client:
        response = await client.get("/__mock__/requests")
    assert response.status_code == 200, response.text
    requests = response.json()["requests"]
    assert isinstance(requests, list)
    return cast(list[dict[str, Any]], requests)


async def _wait_for_notification_sent(
    e2e_db: asyncpg.Connection,
    test_settings: TestSettings,
    notification_id: str,
) -> asyncpg.Record:
    notification: asyncpg.Record | None = None
    for _ in range(60):
        notification = await e2e_db.fetchrow(
            """
            SELECT status, attempts, sent_at, last_error
            FROM notifications
            WHERE id = $1
            """,
            notification_id,
        )
        if notification is not None and notification["status"] == "sent":
            return notification
        await _mock_requests(test_settings)
    assert notification is not None
    pytest.fail(
        f"Worker did not send notification {notification_id}: "
        f"status={notification['status']}, attempts={notification['attempts']}, "
        f"last_error={notification['last_error']}"
    )


@pytest.mark.e2e
async def test_contact_notification_is_deduplicated_and_delivered_once(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory: Any,
    test_settings: TestSettings,
) -> None:
    contact_notification_text = "Исполнитель просит связаться по заказу."
    customer, performer, order = await _confirm_direct_order(
        direct_order_factory,
        e2e_client,
        e2e_db,
        test_settings,
    )
    before_requests = await _mock_requests(test_settings)

    first_response = await e2e_client.post(
        f"/api/customers/by-telegram/{customer['telegram_id']}/contact-requests",
        json={"order_id": order["id"]},
    )
    assert first_response.status_code == 201, first_response.text

    second_response = await e2e_client.post(
        f"/api/customers/by-telegram/{customer['telegram_id']}/contact-requests",
        json={"order_id": order["id"]},
    )
    assert second_response.status_code == 201, second_response.text
    assert second_response.json() == first_response.json()

    notification = await e2e_db.fetchrow(
        """
        SELECT id, status, attempts, sent_at, last_error, deduplication_key
        FROM notifications
        WHERE type = 'contact_request_created'
          AND entity_id = $1
        """,
        first_response.json()["id"],
    )
    assert notification is not None
    assert notification["deduplication_key"] == (
        f"contact-request:{first_response.json()['id']}"
    )

    notification_id = str(notification["id"])
    await e2e_db.execute(
        """
        UPDATE notifications
        SET scheduled_at = now() - interval '1 minute'
        WHERE id = $1 AND status = 'pending'
        """,
        notification_id,
    )
    delivered_notification = await _wait_for_notification_sent(
        e2e_db,
        test_settings,
        notification_id,
    )
    final_requests = await _mock_requests(test_settings)
    target_requests = [
        request
        for request in final_requests
        if request["path"] == "/bottest-executor-token/sendMessage"
        and json.loads(request["body"])["chat_id"] == performer["telegram_id"]
        and contact_notification_text in json.loads(request["body"])["text"]
    ]
    before_target_requests = [
        request
        for request in before_requests
        if request["path"] == "/bottest-executor-token/sendMessage"
        and json.loads(request["body"])["chat_id"] == performer["telegram_id"]
        and contact_notification_text in json.loads(request["body"])["text"]
    ]
    assert len(target_requests) - len(before_target_requests) == 1

    notification = await e2e_db.fetchrow(
        """
        SELECT status, attempts, sent_at, last_error
        FROM notifications
        WHERE id = $1
        """,
        notification_id,
    )
    assert notification == delivered_notification
    assert notification["attempts"] == 1
    assert notification["sent_at"] is not None
    assert notification["last_error"] is None

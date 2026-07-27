import asyncio
import hashlib
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

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


def _webhook_payload(
    *,
    payment_id: str,
    amount: Decimal,
    settings: TestSettings,
    order_id: str | None = None,
    status: str = "CONFIRMED",
    success: bool = True,
    payment_date: datetime | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "TerminalKey": settings.tbank_terminal_key,
        "OrderId": order_id or payment_id,
        "Success": success,
        "Status": status,
        "PaymentId": payment_id,
        "Amount": int(amount * 100),
        "Date": (payment_date or datetime(2026, 1, 1, 10, tzinfo=UTC)).isoformat(),
    }
    payload["Token"] = _sign_payload(payload, settings.tbank_password)
    return payload


async def _prepare_payment(
    direct_order_factory,
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
):
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
    assert payment["payment_id"]
    payment_row = await e2e_db.fetchrow(
        "SELECT provider_payment_id, expires_at FROM payments WHERE id = $1",
        payment["payment_id"],
    )
    assert payment_row
    payment["provider_payment_id"] = payment_row["provider_payment_id"]
    payment["expires_at"] = payment_row["expires_at"]
    return customer, order, payment


async def _force_payment_deadline(
    e2e_db: asyncpg.Connection,
    order_id: str,
    *,
    matching_deadline_in_future: bool,
) -> str:
    row = await e2e_db.fetchrow(
        "SELECT selected_match_id FROM orders WHERE id = $1",
        order_id,
    )
    assert row and row["selected_match_id"]
    now = datetime.now(UTC)
    matching_deadline = now + timedelta(minutes=5)
    if not matching_deadline_in_future:
        matching_deadline = now - timedelta(seconds=5)
    await e2e_db.execute(
        """
        UPDATE orders
        SET payment_deadline_at = $2, matching_deadline_at = $3
        WHERE id = $1
        """,
        order_id,
        now - timedelta(seconds=5),
        matching_deadline,
    )
    return str(row["selected_match_id"])


async def _wait_for_payment_deadline_transition(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    *,
    order_id: str,
    customer_id: str,
    expected_order_status: str,
) -> dict[str, Any]:
    for _ in range(40):
        status_response = await e2e_client.get(
            f"/api/payments/orders/{order_id}/status",
            params={"customer_id": customer_id},
        )
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        payment_status = await e2e_db.fetchval(
            """
            SELECT status
            FROM payments
            WHERE order_id = $1
            ORDER BY attempt_number DESC
            LIMIT 1
            """,
            order_id,
        )
        if (
            status["order_status"] == expected_order_status
            and payment_status == "expired"
        ):
            return status
        with suppress(TimeoutError):
            await asyncio.wait_for(asyncio.Event().wait(), timeout=0.25)
    pytest.fail(
        f"Worker did not expire payment for order {order_id}; "
        f"last status={status_response.json()} payment_status={payment_status}"
    )


@pytest.mark.e2e
async def test_successful_payment_webhook_confirms_order_and_is_idempotent(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
    test_settings: TestSettings,
) -> None:
    customer, order, payment = await _prepare_payment(
        direct_order_factory,
        e2e_client,
        e2e_db,
    )
    amount = Decimal(str(order["total_amount"]))
    payload = _webhook_payload(
        payment_id=payment["provider_payment_id"],
        amount=amount,
        settings=test_settings,
        order_id=payment["payment_id"],
    )

    first_response = await e2e_client.post(
        "/api/payments/webhooks/tbank",
        json=payload,
    )
    assert first_response.status_code == 200, first_response.text
    assert first_response.text == "OK"

    status_response = await e2e_client.get(
        f"/api/payments/orders/{order['id']}/status",
        params={"customer_id": customer.entity_id},
    )
    assert status_response.status_code == 200, status_response.text
    status = status_response.json()
    assert status["order_status"] == "confirmed"
    assert status["payment_id"] == payment["payment_id"]
    assert status["payment_status"] == "succeeded"

    history_count = await e2e_db.fetchval(
        """
        SELECT count(*)
        FROM order_status_history
        WHERE order_id = $1 AND to_status = 'confirmed'
        """,
        order["id"],
    )
    notification_count = await e2e_db.fetchval(
        """
        SELECT count(*)
        FROM notifications
        WHERE entity_id = $1
          AND type IN ('payment_success', 'order_confirmed')
        """,
        order["id"],
    )
    assert history_count == 1
    assert notification_count == 2

    second_response = await e2e_client.post(
        "/api/payments/webhooks/tbank",
        json=payload,
    )
    assert second_response.status_code == 200, second_response.text
    assert second_response.text == "OK"

    assert (
        await e2e_db.fetchval(
            """
            SELECT count(*)
            FROM order_status_history
            WHERE order_id = $1 AND to_status = 'confirmed'
            """,
            order["id"],
        )
        == 1
    )
    assert (
        await e2e_db.fetchval(
            """
            SELECT count(*)
            FROM notifications
            WHERE entity_id = $1
              AND type IN ('payment_success', 'order_confirmed')
            """,
            order["id"],
        )
        == 2
    )


@pytest.mark.e2e
async def test_payment_webhook_rejects_invalid_signature_and_terminal(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
    test_settings: TestSettings,
) -> None:
    _, order, payment = await _prepare_payment(
        direct_order_factory,
        e2e_client,
        e2e_db,
    )
    amount = Decimal(str(order["total_amount"]))
    payload = _webhook_payload(
        payment_id=payment["provider_payment_id"],
        amount=amount,
        settings=test_settings,
        order_id=payment["payment_id"],
    )

    invalid_token = {**payload, "Token": "invalid-token"}
    invalid_token_response = await e2e_client.post(
        "/api/payments/webhooks/tbank",
        json=invalid_token,
    )
    assert invalid_token_response.status_code == 403

    invalid_terminal = {**payload, "TerminalKey": "wrong-terminal"}
    invalid_terminal_response = await e2e_client.post(
        "/api/payments/webhooks/tbank",
        json=invalid_terminal,
    )
    assert invalid_terminal_response.status_code == 403

    status_response = await e2e_client.get(
        f"/api/payments/orders/{order['id']}/status",
        params={"customer_id": order["customer_id"]},
    )
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["order_status"] == "waiting_payment"


@pytest.mark.e2e
@pytest.mark.parametrize(
    ("payload_update", "expected_status"),
    [
        ({"PaymentId": None}, 400),
        ({"OrderId": "not-a-uuid"}, 400),
        pytest.param(
            {"Amount": "not-an-integer"},
            400,
        ),
    ],
)
async def test_payment_webhook_rejects_invalid_payload(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
    test_settings: TestSettings,
    payload_update: dict[str, Any],
    expected_status: int,
) -> None:
    _, order, payment = await _prepare_payment(
        direct_order_factory,
        e2e_client,
        e2e_db,
    )
    payload = _webhook_payload(
        payment_id=payment["provider_payment_id"],
        amount=Decimal(str(order["total_amount"])),
        settings=test_settings,
        order_id=payment["payment_id"],
    )
    payload.update(payload_update)
    if payload.get("PaymentId") is not None or payload.get("OrderId") != "not-a-uuid":
        payload["Token"] = _sign_payload(payload, test_settings.tbank_password)

    payment_before = await e2e_db.fetchrow(
        "SELECT status, provider_status FROM payments WHERE id = $1",
        payment["payment_id"],
    )
    history_before = await e2e_db.fetchval(
        "SELECT count(*) FROM order_status_history WHERE order_id = $1",
        order["id"],
    )
    notifications_before = await e2e_db.fetchval(
        "SELECT count(*) FROM notifications WHERE entity_id = $1",
        order["id"],
    )

    response = await e2e_client.post(
        "/api/payments/webhooks/tbank",
        json=payload,
    )
    assert response.status_code == expected_status, response.text

    assert (
        await e2e_db.fetchrow(
            "SELECT status, provider_status FROM payments WHERE id = $1",
            payment["payment_id"],
        )
        == payment_before
    )
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM order_status_history WHERE order_id = $1",
            order["id"],
        )
        == history_before
    )
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM notifications WHERE entity_id = $1",
            order["id"],
        )
        == notifications_before
    )


@pytest.mark.e2e
async def test_rejected_payment_webhook_does_not_confirm_order(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
    test_settings: TestSettings,
) -> None:
    _, order, payment = await _prepare_payment(
        direct_order_factory,
        e2e_client,
        e2e_db,
    )
    payload = _webhook_payload(
        payment_id=payment["provider_payment_id"],
        amount=Decimal(str(order["total_amount"])),
        settings=test_settings,
        order_id=payment["payment_id"],
        status="REJECTED",
        success=False,
    )

    response = await e2e_client.post(
        "/api/payments/webhooks/tbank",
        json=payload,
    )
    assert response.status_code == 200, response.text

    status_response = await e2e_client.get(
        f"/api/payments/orders/{order['id']}/status",
        params={"customer_id": order["customer_id"]},
    )
    assert status_response.status_code == 200, status_response.text
    status = status_response.json()
    assert status["order_status"] == "waiting_payment"
    assert status["payment_status"] == "failed"


@pytest.mark.e2e
async def test_customer_can_retry_failed_payment_and_old_webhook_is_ignored(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
    test_settings: TestSettings,
) -> None:
    customer, order, payment = await _prepare_payment(
        direct_order_factory,
        e2e_client,
        e2e_db,
    )
    amount = Decimal(str(order["total_amount"]))
    rejected_payload = _webhook_payload(
        payment_id=payment["provider_payment_id"],
        amount=amount,
        settings=test_settings,
        order_id=payment["payment_id"],
        status="REJECTED",
        success=False,
    )
    rejected_response = await e2e_client.post(
        "/api/payments/webhooks/tbank",
        json=rejected_payload,
    )
    assert rejected_response.status_code == 200, rejected_response.text

    retry_response = await e2e_client.post(
        f"/api/payments/orders/{order['id']}/retry",
        params={"customer_id": customer.entity_id},
    )
    assert retry_response.status_code == 200, retry_response.text
    retry_status = retry_response.json()
    assert retry_status["order_status"] == "waiting_payment"
    assert retry_status["payment_status"] == "pending"
    assert retry_status["attempts_used"] == 2
    assert retry_status["retry_available"] is False
    assert retry_status["payment_id"] != payment["payment_id"]

    order_row = await e2e_db.fetchrow(
        "SELECT selected_match_id, active_payment_id FROM orders WHERE id = $1",
        order["id"],
    )
    assert order_row
    assert str(order_row["active_payment_id"]) == retry_status["payment_id"]
    assert order_row["selected_match_id"] is not None

    old_success_payload = _webhook_payload(
        payment_id=payment["provider_payment_id"],
        amount=amount,
        settings=test_settings,
        order_id=payment["payment_id"],
    )
    old_success_response = await e2e_client.post(
        "/api/payments/webhooks/tbank",
        json=old_success_payload,
    )
    assert old_success_response.status_code == 200, old_success_response.text
    status_response = await e2e_client.get(
        f"/api/payments/orders/{order['id']}/status",
        params={"customer_id": customer.entity_id},
    )
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["order_status"] == "waiting_payment"

    new_provider_payment_id = await e2e_db.fetchval(
        "SELECT provider_payment_id FROM payments WHERE id = $1",
        retry_status["payment_id"],
    )
    assert new_provider_payment_id
    success_response = await e2e_client.post(
        "/api/payments/webhooks/tbank",
        json=_webhook_payload(
            payment_id=new_provider_payment_id,
            amount=amount,
            settings=test_settings,
            order_id=retry_status["payment_id"],
        ),
    )
    assert success_response.status_code == 200, success_response.text
    final_status = await e2e_client.get(
        f"/api/payments/orders/{order['id']}/status",
        params={"customer_id": customer.entity_id},
    )
    assert final_status.status_code == 200, final_status.text
    assert final_status.json()["order_status"] == "confirmed"
    assert final_status.json()["payment_id"] == retry_status["payment_id"]


@pytest.mark.e2e
async def test_customer_payment_retry_is_limited_to_three_attempts(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
    test_settings: TestSettings,
) -> None:
    customer, order, payment = await _prepare_payment(
        direct_order_factory,
        e2e_client,
        e2e_db,
    )
    amount = Decimal(str(order["total_amount"]))
    current_payment_id = payment["payment_id"]
    current_provider_payment_id = payment["provider_payment_id"]

    for expected_attempt_number in (1, 2, 3):
        rejected_response = await e2e_client.post(
            "/api/payments/webhooks/tbank",
            json=_webhook_payload(
                payment_id=current_provider_payment_id,
                amount=amount,
                settings=test_settings,
                order_id=current_payment_id,
                status="REJECTED",
                success=False,
            ),
        )
        assert rejected_response.status_code == 200, rejected_response.text

        status_response = await e2e_client.get(
            f"/api/payments/orders/{order['id']}/status",
            params={"customer_id": customer.entity_id},
        )
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status["order_status"] == "waiting_payment"
        assert status["attempts_used"] == expected_attempt_number

        if expected_attempt_number == 3:
            assert status["retry_available"] is False
            retry_response = await e2e_client.post(
                f"/api/payments/orders/{order['id']}/retry",
                params={"customer_id": customer.entity_id},
            )
            assert retry_response.status_code == 409, retry_response.text
            continue

        retry_response = await e2e_client.post(
            f"/api/payments/orders/{order['id']}/retry",
            params={"customer_id": customer.entity_id},
        )
        assert retry_response.status_code == 200, retry_response.text
        retry_status = retry_response.json()
        assert retry_status["attempts_used"] == expected_attempt_number + 1
        current_payment_id = retry_status["payment_id"]
        current_provider_payment_id = await e2e_db.fetchval(
            "SELECT provider_payment_id FROM payments WHERE id = $1",
            current_payment_id,
        )
        assert current_provider_payment_id

    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM payments WHERE order_id = $1",
            order["id"],
        )
        == 3
    )


@pytest.mark.e2e
async def test_payment_webhook_with_mismatched_amount_is_not_applied(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
    test_settings: TestSettings,
) -> None:
    _, order, payment = await _prepare_payment(
        direct_order_factory,
        e2e_client,
        e2e_db,
    )
    amount = Decimal(str(order["total_amount"])) + Decimal("1.00")
    payload = _webhook_payload(
        payment_id=payment["provider_payment_id"],
        amount=amount,
        settings=test_settings,
        order_id=payment["payment_id"],
    )

    response = await e2e_client.post(
        "/api/payments/webhooks/tbank",
        json=payload,
    )
    assert response.status_code == 200, response.text

    status_response = await e2e_client.get(
        f"/api/payments/orders/{order['id']}/status",
        params={"customer_id": order["customer_id"]},
    )
    assert status_response.status_code == 200, status_response.text
    status = status_response.json()
    assert status["order_status"] == "waiting_payment"
    assert status["payment_status"] == "succeeded_unapplied"


@pytest.mark.e2e
async def test_expired_payment_webhook_is_not_applied(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
    test_settings: TestSettings,
) -> None:
    _, order, payment = await _prepare_payment(
        direct_order_factory,
        e2e_client,
        e2e_db,
    )
    expired_at = payment["expires_at"] + timedelta(seconds=1)
    payload = _webhook_payload(
        payment_id=payment["provider_payment_id"],
        amount=Decimal(str(order["total_amount"])),
        settings=test_settings,
        order_id=payment["payment_id"],
        payment_date=expired_at,
    )

    response = await e2e_client.post(
        "/api/payments/webhooks/tbank",
        json=payload,
    )
    assert response.status_code == 200, response.text

    status_response = await e2e_client.get(
        f"/api/payments/orders/{order['id']}/status",
        params={"customer_id": order["customer_id"]},
    )
    assert status_response.status_code == 200, status_response.text
    status = status_response.json()
    assert status["order_status"] == "waiting_payment"
    assert status["payment_status"] == "succeeded_unapplied"


@pytest.mark.e2e
async def test_worker_expiring_payment_returns_order_to_searching(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
) -> None:
    customer, _, order = await direct_order_factory()
    matches_response = await e2e_client.get(
        f"/api/orders/{order['id']}/matches",
        params={"customer_id": customer.entity_id},
    )
    assert matches_response.status_code == 200, matches_response.text
    match = matches_response.json()[0]
    accept_response = await e2e_client.post(
        f"/api/orders/matches/{match['id']}/direct/accept",
        json={"performer_id": match["performer_id"]},
    )
    assert accept_response.status_code == 200, accept_response.text

    selected_match_id = await _force_payment_deadline(
        e2e_db,
        order["id"],
        matching_deadline_in_future=True,
    )
    status = await _wait_for_payment_deadline_transition(
        e2e_client,
        e2e_db,
        order_id=order["id"],
        customer_id=customer.entity_id,
        expected_order_status="searching",
    )

    assert status["payment_id"] is None
    assert status["payment_status"] is None
    order_row = await e2e_db.fetchrow(
        """
        SELECT active_payment_id, selected_match_id, payment_deadline_at
        FROM orders
        WHERE id = $1
        """,
        order["id"],
    )
    assert order_row
    assert order_row["active_payment_id"] is None
    assert order_row["selected_match_id"] is None
    assert order_row["payment_deadline_at"] is None

    payment_row = await e2e_db.fetchrow(
        "SELECT status FROM payments WHERE order_id = $1",
        order["id"],
    )
    assert payment_row and payment_row["status"] == "expired"
    match_row = await e2e_db.fetchrow(
        "SELECT status, close_reason FROM order_matches WHERE id = $1",
        selected_match_id,
    )
    assert match_row is not None
    assert dict(match_row) == {
        "status": "expired",
        "close_reason": "payment_deadline",
    }
    assert (
        await e2e_db.fetchval(
            """
            SELECT count(*)
            FROM order_status_history
            WHERE order_id = $1
              AND from_status = 'waiting_payment'
              AND to_status = 'searching'
              AND reason = 'payment_deadline'
            """,
            order["id"],
        )
        == 1
    )
    notification = await e2e_db.fetchrow(
        """
        SELECT type, deduplication_key
        FROM notifications
        WHERE entity_type = 'order' AND entity_id = $1
          AND type = 'payment_expired_order_searching'
        """,
        order["id"],
    )
    assert notification is not None
    assert dict(notification) == {
        "type": "payment_expired_order_searching",
        "deduplication_key": f"payment_expired_order_searching:{order['id']}",
    }


@pytest.mark.e2e
async def test_worker_expiring_payment_expires_order_after_matching_deadline(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
) -> None:
    customer, _, order = await direct_order_factory()
    matches_response = await e2e_client.get(
        f"/api/orders/{order['id']}/matches",
        params={"customer_id": customer.entity_id},
    )
    assert matches_response.status_code == 200, matches_response.text
    match = matches_response.json()[0]
    accept_response = await e2e_client.post(
        f"/api/orders/matches/{match['id']}/direct/accept",
        json={"performer_id": match["performer_id"]},
    )
    assert accept_response.status_code == 200, accept_response.text

    selected_match_id = await _force_payment_deadline(
        e2e_db,
        order["id"],
        matching_deadline_in_future=False,
    )
    status = await _wait_for_payment_deadline_transition(
        e2e_client,
        e2e_db,
        order_id=order["id"],
        customer_id=customer.entity_id,
        expected_order_status="expired",
    )

    assert status["payment_status"] == "expired"
    order_row = await e2e_db.fetchrow(
        "SELECT expired_reason, expired_at FROM orders WHERE id = $1",
        order["id"],
    )
    assert order_row
    assert order_row["expired_reason"] == "payment_deadline_reached"
    assert order_row["expired_at"] is not None
    match_row = await e2e_db.fetchrow(
        "SELECT status, close_reason FROM order_matches WHERE id = $1",
        selected_match_id,
    )
    assert match_row is not None
    assert dict(match_row) == {
        "status": "expired",
        "close_reason": "payment_deadline",
    }
    assert (
        await e2e_db.fetchval(
            """
            SELECT count(*)
            FROM order_status_history
            WHERE order_id = $1
              AND from_status = 'waiting_payment'
              AND to_status = 'expired'
              AND reason = 'payment_deadline'
            """,
            order["id"],
        )
        == 1
    )
    notification = await e2e_db.fetchrow(
        """
        SELECT type, deduplication_key
        FROM notifications
        WHERE entity_type = 'order' AND entity_id = $1
          AND type = 'payment_expired_order_expired'
        """,
        order["id"],
    )
    assert notification is not None
    assert dict(notification) == {
        "type": "payment_expired_order_expired",
        "deduplication_key": f"payment_expired_order_expired:{order['id']}",
    }


@pytest.mark.e2e
async def test_unknown_provider_payment_is_not_applied(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
    test_settings: TestSettings,
) -> None:
    _, order, payment = await _prepare_payment(
        direct_order_factory,
        e2e_client,
        e2e_db,
    )
    payload = _webhook_payload(
        payment_id="unknown-provider-payment",
        amount=Decimal(str(order["total_amount"])),
        settings=test_settings,
        order_id=payment["payment_id"],
    )

    response = await e2e_client.post(
        "/api/payments/webhooks/tbank",
        json=payload,
    )
    assert response.status_code == 404, response.text

    status_response = await e2e_client.get(
        f"/api/payments/orders/{order['id']}/status",
        params={"customer_id": order["customer_id"]},
    )
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["order_status"] == "waiting_payment"


@pytest.mark.e2e
async def test_old_payment_attempt_is_not_applied_to_active_order_payment(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
    test_settings: TestSettings,
) -> None:
    _, order, payment = await _prepare_payment(
        direct_order_factory,
        e2e_client,
        e2e_db,
    )
    current_payment = await e2e_db.fetchrow(
        """
        SELECT order_id, performer_id, amount, expires_at
        FROM payments
        WHERE id = $1
        """,
        payment["payment_id"],
    )
    assert current_payment
    old_payment_id = uuid4()
    old_provider_payment_id = f"stale-provider-{old_payment_id}"
    await e2e_db.execute(
        """
        INSERT INTO payments (
            id, order_id, performer_id, attempt_number, provider,
            provider_payment_id, idempotency_key, amount, status,
            provider_status, confirmation_url, expires_at, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $13
        )
        """,
        old_payment_id,
        current_payment["order_id"],
        current_payment["performer_id"],
        2,
        "tbank_test",
        old_provider_payment_id,
        f"stale-payment:{old_payment_id}",
        current_payment["amount"],
        "expired",
        "DEADLINE_EXPIRED",
        "https://pay.test/stale",
        current_payment["expires_at"],
        datetime.now(UTC),
    )
    payload = _webhook_payload(
        payment_id=old_provider_payment_id,
        amount=Decimal(str(order["total_amount"])),
        settings=test_settings,
        order_id=str(old_payment_id),
    )

    response = await e2e_client.post(
        "/api/payments/webhooks/tbank",
        json=payload,
    )
    assert response.status_code == 200, response.text

    stale_payment = await e2e_db.fetchrow(
        "SELECT status, unapplied_reason FROM payments WHERE id = $1",
        old_payment_id,
    )
    assert stale_payment
    assert stale_payment["status"] == "expired"
    status_response = await e2e_client.get(
        f"/api/payments/orders/{order['id']}/status",
        params={"customer_id": order["customer_id"]},
    )
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["order_status"] == "waiting_payment"


@pytest.mark.e2e
async def test_admin_retry_check_marks_rejected_provider_payment_failed(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
    test_settings: TestSettings,
) -> None:
    _, order, payment = await _prepare_payment(
        direct_order_factory,
        e2e_client,
        e2e_db,
    )
    assert payment["confirmation_url"]
    async with httpx.AsyncClient(follow_redirects=False) as payment_client:
        payment_response = await payment_client.post(
            f"{payment['confirmation_url']}/submit",
            data={
                "pan": "2201382000000062",
                "exp_date": "12/30",
                "cvv": "123",
                "cardholder": "E2E CUSTOMER",
            },
        )
    assert payment_response.status_code == 200, payment_response.text
    login_response = await e2e_client.post(
        "/admin/login",
        json={
            "email": test_settings.default_admin_email,
            "password": test_settings.default_admin_password,
        },
    )
    assert login_response.status_code == 200, login_response.text
    csrf_token = login_response.json()["csrf_token"]

    retry_response = await e2e_client.post(
        f"/admin/payments/{payment['payment_id']}/retry-check",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert retry_response.status_code == 200, retry_response.text
    assert retry_response.json() == {
        "status": "checked",
        "applied": False,
        "unapplied_reason": None,
    }

    status_response = await e2e_client.get(
        f"/api/payments/orders/{order['id']}/status",
        params={"customer_id": order["customer_id"]},
    )
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["payment_status"] == "failed"

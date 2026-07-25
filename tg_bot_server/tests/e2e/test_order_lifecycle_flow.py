import base64
import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

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
    direct_order_factory,
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


@pytest.mark.e2e
async def test_confirmed_order_completes_full_execution_lifecycle(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
    test_settings: TestSettings,
) -> None:
    customer, performer, order = await _confirm_direct_order(
        direct_order_factory,
        e2e_client,
        e2e_db,
        test_settings,
    )

    start_response = await e2e_client.post(
        f"/api/orders/{order['id']}/start",
        json={"performer_id": performer["entity_id"]},
    )
    assert start_response.status_code == 200, start_response.text
    assert start_response.json()["status"] == "in_progress"

    finish_response = await e2e_client.post(
        f"/api/orders/{order['id']}/finish",
        json={"performer_id": performer["entity_id"]},
    )
    assert finish_response.status_code == 200, finish_response.text
    assert finish_response.json()["status"] == "waiting_report"

    upload_response = await e2e_client.post(
        f"/api/performers/by-telegram/{performer['telegram_id']}/files",
        files={
            "file": (
                "report.png",
                base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
                ),
                "image/png",
            )
        },
    )
    assert upload_response.status_code == 201, upload_response.text
    report_file_id = upload_response.json()["id"]

    report_response = await e2e_client.post(
        f"/api/orders/{order['id']}/report",
        json={
            "performer_id": performer["entity_id"],
            "completed_work": "Уход выполнен по плану",
            "comment": "Все договорённости соблюдены",
            "problem_flag": False,
            "file_ids": [report_file_id],
        },
    )
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()
    assert report["order_id"] == order["id"]
    assert report["performer_id"] == performer["entity_id"]
    assert report["completed_work"] == "Уход выполнен по плану"
    assert report["problem_flag"] is False
    assert report["file_ids"] == [report_file_id]

    customer_report_response = await e2e_client.get(
        f"/api/orders/customer/{customer['entity_id']}/my/{order['id']}/report",
    )
    assert customer_report_response.status_code == 200, customer_report_response.text
    assert customer_report_response.json()["id"] == report["id"]

    performer_report_response = await e2e_client.get(
        f"/api/orders/performer/{performer['entity_id']}/my/{order['id']}/report",
    )
    assert performer_report_response.status_code == 200, performer_report_response.text
    assert performer_report_response.json()["id"] == report["id"]

    confirm_response = await e2e_client.post(
        f"/api/orders/customer/{customer['entity_id']}/my/{order['id']}/confirm-report",
    )
    assert confirm_response.status_code == 200, confirm_response.text
    assert confirm_response.json()["status"] == "completed"

    transitions = await e2e_db.fetch(
        """
        SELECT from_status, to_status, actor_type, reason
        FROM order_status_history
        WHERE order_id = $1
          AND to_status IN (
              'confirmed', 'in_progress', 'waiting_report',
              'report_submitted', 'completed'
          )
        ORDER BY created_at
        """,
        order["id"],
    )
    assert [(row["from_status"], row["to_status"]) for row in transitions] == [
        ("waiting_payment", "confirmed"),
        ("confirmed", "in_progress"),
        ("in_progress", "waiting_report"),
        ("waiting_report", "report_submitted"),
        ("report_submitted", "completed"),
    ]
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM order_reports WHERE order_id = $1",
            order["id"],
        )
        == 1
    )


@pytest.mark.e2e
async def test_non_selected_performer_cannot_start_confirmed_order(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    direct_order_factory,
    performer_factory,
    test_settings: TestSettings,
) -> None:
    customer, performer, order = await _confirm_direct_order(
        direct_order_factory,
        e2e_client,
        e2e_db,
        test_settings,
    )
    other_performer = await performer_factory()

    start_response = await e2e_client.post(
        f"/api/orders/{order['id']}/start",
        json={"performer_id": other_performer.entity_id},
    )
    assert start_response.status_code == 404, start_response.text

    status_response = await e2e_client.get(
        f"/api/payments/orders/{order['id']}/status",
        params={"customer_id": customer["entity_id"]},
    )
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["order_status"] == "confirmed"
    assert status_response.json()["payment_status"] == "succeeded"
    assert performer["entity_id"] != other_performer.entity_id

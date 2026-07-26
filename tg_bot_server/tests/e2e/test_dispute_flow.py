import base64
import json

import asyncpg
import httpx
import pytest

from tests.e2e.test_order_lifecycle_flow import _confirm_direct_order
from tests.support.settings import TestSettings

_REPORT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


@pytest.mark.e2e
async def test_customer_dispute_blocks_payout_and_admin_can_close_it(
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
    finish_response = await e2e_client.post(
        f"/api/orders/{order['id']}/finish",
        json={"performer_id": performer["entity_id"]},
    )
    assert finish_response.status_code == 200, finish_response.text

    upload_response = await e2e_client.post(
        f"/api/performers/by-telegram/{performer['telegram_id']}/files",
        files={"file": ("dispute-report.png", _REPORT_PNG, "image/png")},
    )
    assert upload_response.status_code == 201, upload_response.text
    report_response = await e2e_client.post(
        f"/api/orders/{order['id']}/report",
        json={
            "performer_id": performer["entity_id"],
            "completed_work": "Работа завершена",
            "file_ids": [upload_response.json()["id"]],
        },
    )
    assert report_response.status_code == 200, report_response.text
    assert report_response.json()["order_id"] == order["id"]

    dispute_response = await e2e_client.post(
        f"/api/customers/by-telegram/{customer['telegram_id']}/disputes",
        json={
            "order_id": order["id"],
            "text": "Работа не соответствует договорённости",
        },
    )
    assert dispute_response.status_code == 201, dispute_response.text
    dispute = dispute_response.json()
    assert dispute["kind"] == "dispute"
    assert dispute["status"] == "open"

    repeated_response = await e2e_client.post(
        f"/api/customers/by-telegram/{customer['telegram_id']}/disputes",
        json={"order_id": order["id"], "text": "Повторная отправка"},
    )
    assert repeated_response.status_code == 201, repeated_response.text
    assert repeated_response.json()["id"] == dispute["id"]

    blocked_row = await e2e_db.fetchrow(
        "SELECT payout_status, payout_block_reason FROM orders WHERE id = $1",
        order["id"],
    )
    assert blocked_row is not None
    assert dict(blocked_row) == {
        "payout_status": "blocked",
        "payout_block_reason": "customer_dispute",
    }

    login_response = await e2e_client.post(
        "/admin/login",
        json={
            "email": test_settings.default_admin_email,
            "password": test_settings.default_admin_password,
        },
    )
    assert login_response.status_code == 200, login_response.text
    csrf_token = login_response.json()["csrf_token"]
    admin_list_response = await e2e_client.get("/admin/support/dispute")
    assert admin_list_response.status_code == 200, admin_list_response.text
    assert any(
        item["id"] == dispute["id"] for item in admin_list_response.json()["items"]
    )

    close_response = await e2e_client.patch(
        f"/admin/support/dispute/{dispute['id']}",
        headers={"X-CSRF-Token": csrf_token},
        json={"status": "closed", "admin_comment": "Решение проверено"},
    )
    assert close_response.status_code == 200, close_response.text
    assert close_response.json()["status"] == "closed"

    ready_row = await e2e_db.fetchrow(
        "SELECT payout_status, payout_block_reason FROM orders WHERE id = $1",
        order["id"],
    )
    assert ready_row is not None
    assert dict(ready_row) == {
        "payout_status": "ready",
        "payout_block_reason": None,
    }
    audit = await e2e_db.fetchrow(
        """
        SELECT action, entity_type, entity_id, audit_metadata
        FROM admin_audit_logs
        WHERE entity_type = 'dispute' AND entity_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        dispute["id"],
    )
    assert audit is not None
    assert audit["action"] == "update_support_record"
    assert audit["entity_type"] == "dispute"
    assert str(audit["entity_id"]) == dispute["id"]
    audit_metadata = audit["audit_metadata"]
    if isinstance(audit_metadata, str):
        audit_metadata = json.loads(audit_metadata)
    assert audit_metadata == {
        "status": "closed",
        "admin_comment": "Решение проверено",
    }

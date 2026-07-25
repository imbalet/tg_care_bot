import asyncio
import json
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import asyncpg
import httpx
import pytest

from tests.support.settings import TestSettings


async def _insert_invitation_notification(
    e2e_db: asyncpg.Connection,
    *,
    recipient_telegram_id: int,
    deduplication_key: str,
) -> str:
    notification_id = uuid4()
    now = datetime.now(UTC)
    await e2e_db.execute(
        """
        INSERT INTO notifications (
            id, recipient_type, recipient_telegram_id, channel, type,
            entity_type, entity_id, payload, deduplication_key, status,
            attempts, scheduled_at, delete_after, created_at, updated_at
        ) VALUES (
            $1, 'performer_invitation', $2, 'telegram', 'direct_invitation_created',
            'performer_invitation', $1, $3::jsonb, $4, 'pending',
            0, $5, $6, $5, $5
        )
        """,
        notification_id,
        recipient_telegram_id,
        '{"invitation_id": "e2e"}',
        deduplication_key,
        now - timedelta(minutes=1),
        now + timedelta(days=1),
    )
    return str(notification_id)


async def _insert_invitation_notifications(
    e2e_db: asyncpg.Connection,
    *,
    count: int,
) -> tuple[str, ...]:
    return tuple(
        [
            await _insert_invitation_notification(
                e2e_db,
                recipient_telegram_id=940000000 + index,
                deduplication_key=f"e2e-worker-concurrent-{uuid4().hex}",
            )
            for index in range(count)
        ]
    )


async def _wait_for_notification(
    e2e_db: asyncpg.Connection,
    notification_id: str,
    expected_status: str,
) -> asyncpg.Record:
    notification: asyncpg.Record | None = None
    for _ in range(80):
        notification = await e2e_db.fetchrow(
            """
            SELECT status, attempts, sent_at, claimed_at, last_error
            FROM notifications
            WHERE id = $1
            """,
            notification_id,
        )
        if notification is not None and notification["status"] == expected_status:
            return notification
        with suppress(TimeoutError):
            await asyncio.wait_for(asyncio.Event().wait(), timeout=0.25)
    assert notification is not None
    pytest.fail(
        f"Notification {notification_id} did not reach {expected_status}: "
        f"status={notification['status']}, attempts={notification['attempts']}, "
        f"last_error={notification['last_error']}"
    )


@pytest.mark.e2e
async def test_worker_claims_and_delivers_outbox_notification(
    e2e_db: asyncpg.Connection,
) -> None:
    notification_id = await _insert_invitation_notification(
        e2e_db,
        recipient_telegram_id=930000001,
        deduplication_key=f"e2e-worker-success-{uuid4().hex}",
    )

    notification = await _wait_for_notification(e2e_db, notification_id, "sent")
    assert notification["attempts"] == 1
    assert notification["sent_at"] is not None
    assert notification["claimed_at"] is None
    assert notification["last_error"] is None


@pytest.mark.e2e
async def test_worker_retries_and_marks_terminal_outbox_failure(
    e2e_db: asyncpg.Connection,
) -> None:
    notification_id = await _insert_invitation_notification(
        e2e_db,
        recipient_telegram_id=999999999,
        deduplication_key=f"e2e-worker-failure-{uuid4().hex}",
    )

    notification = await _wait_for_notification(e2e_db, notification_id, "failed")
    assert notification["attempts"] == 3
    assert notification["sent_at"] is None
    assert notification["claimed_at"] is None
    assert notification["last_error"] == "RuntimeError"


@pytest.mark.e2e
async def test_worker_does_not_reprocess_terminal_outbox_failure(
    e2e_db: asyncpg.Connection,
    test_settings: TestSettings,
) -> None:
    notification_id = await _insert_invitation_notification(
        e2e_db,
        recipient_telegram_id=999999999,
        deduplication_key=f"e2e-worker-terminal-{uuid4().hex}",
    )
    await _wait_for_notification(e2e_db, notification_id, "failed")

    async with httpx.AsyncClient(
        base_url=test_settings.telegram_api_base_url,
        timeout=test_settings.e2e_request_timeout_seconds,
    ) as client:
        before = len((await client.get("/__mock__/requests")).json()["requests"])
    async with httpx.AsyncClient(
        base_url=test_settings.telegram_api_base_url,
        timeout=test_settings.e2e_request_timeout_seconds,
    ) as client:
        after = len((await client.get("/__mock__/requests")).json()["requests"])

    notification = await e2e_db.fetchrow(
        "SELECT status, attempts FROM notifications WHERE id = $1",
        notification_id,
    )
    assert notification is not None
    assert dict(notification) == {"status": "failed", "attempts": 3}
    assert after == before


@pytest.mark.e2e
async def test_two_workers_claim_outbox_batch_without_duplicate_delivery(
    e2e_db: asyncpg.Connection,
    test_settings: TestSettings,
) -> None:
    notification_ids = await _insert_invitation_notifications(e2e_db, count=100)

    for _ in range(120):
        completed = await e2e_db.fetchval(
            """
            SELECT count(*)
            FROM notifications
            WHERE id = ANY($1::uuid[]) AND status = 'sent'
            """,
            list(notification_ids),
        )
        if completed == len(notification_ids):
            break
        with suppress(TimeoutError):
            await asyncio.wait_for(asyncio.Event().wait(), timeout=0.25)
    else:
        pytest.fail(f"Only {completed} of {len(notification_ids)} notifications sent")

    rows = await e2e_db.fetch(
        """
        SELECT status, attempts, sent_at, claimed_at
        FROM notifications
        WHERE id = ANY($1::uuid[])
        """,
        list(notification_ids),
    )
    assert len(rows) == len(notification_ids)
    assert all(
        row["status"] == "sent"
        and row["attempts"] == 1
        and row["sent_at"] is not None
        and row["claimed_at"] is None
        for row in rows
    )

    async with httpx.AsyncClient(
        base_url=test_settings.telegram_api_base_url,
        timeout=test_settings.e2e_request_timeout_seconds,
    ) as client:
        requests = (await client.get("/__mock__/requests")).json()["requests"]
    delivered_chats = [
        json.loads(request["body"])["chat_id"]
        for request in requests
        if request["path"] == "/bottest-executor-token/sendMessage"
        and 940000000 <= json.loads(request["body"])["chat_id"] < 940000100
    ]
    assert sorted(delivered_chats) == list(range(940000000, 940000100))

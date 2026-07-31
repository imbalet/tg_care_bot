from unittest.mock import AsyncMock, Mock, patch

import pytest

from backend.modules.notifications.infrastructure import NotificationModel
from backend.worker.jobs import (
    RetryPolicy,
    _notification_keyboard,
    _notification_text,
    run_with_retry,
)


@pytest.mark.unit
def test_retry_policy_uses_exponential_backoff_with_cap() -> None:
    policy = RetryPolicy(max_attempts=4, base_delay_seconds=1, max_delay_seconds=3)

    assert policy.delay_for_attempt(1) == 1
    assert policy.delay_for_attempt(2) == 2
    assert policy.delay_for_attempt(3) == 3
    assert policy.delay_for_attempt(4) == 3


@pytest.mark.unit
async def test_run_with_retry_retries_then_succeeds() -> None:
    operation = AsyncMock(side_effect=[RuntimeError("temporary"), None])
    logger = Mock()
    policy = RetryPolicy(max_attempts=2, base_delay_seconds=0)

    with patch("backend.worker.jobs.asyncio.sleep", new_callable=AsyncMock):
        await run_with_retry(operation, policy, logger, "test_operation")

    assert operation.await_count == 2
    logger.warning.assert_called_once()
    logger.exception.assert_not_called()


@pytest.mark.unit
async def test_run_with_retry_logs_and_raises_after_max_attempts() -> None:
    error = RuntimeError("permanent")
    operation = AsyncMock(side_effect=error)
    logger = Mock()
    policy = RetryPolicy(max_attempts=2, base_delay_seconds=0)

    with (
        patch("backend.worker.jobs.asyncio.sleep", new_callable=AsyncMock),
        pytest.raises(RuntimeError, match="permanent"),
    ):
        await run_with_retry(operation, policy, logger, "test_operation")

    assert operation.await_count == 2
    logger.exception.assert_called_once()


@pytest.mark.unit
def test_notification_rendering_contains_safe_body_and_actions() -> None:
    notification = NotificationModel(
        recipient_type="performer",
        type="direct_invitation_created",
        payload={"match_id": "00000000-0000-0000-0000-000000000001"},
    )

    text = _notification_text(notification)
    keyboard = _notification_keyboard(notification)

    assert "Исполнитель" in text
    assert keyboard is not None
    assert keyboard["inline_keyboard"]


@pytest.mark.unit
def test_notification_rendering_supports_invitation_and_unknown_action() -> None:
    invitation = NotificationModel(
        recipient_type="performer_invitation",
        type="performer_invitation_created",
        payload={},
    )
    unknown = NotificationModel(
        recipient_type="admin",
        type="unknown",
        payload={},
    )

    assert "/start" in _notification_text(invitation)
    assert _notification_keyboard(unknown) is None


@pytest.mark.unit
def test_notification_rendering_shows_short_order_id() -> None:
    notification = NotificationModel(
        recipient_type="customer",
        type="order_started",
        payload={"order_id": "12345678-1234-1234-1234-123456789abc"},
    )

    text = _notification_text(notification)

    assert "Заказ: #12345678" in text
    assert "12345678-1234" not in text


@pytest.mark.unit
def test_notification_rendering_explains_who_cancelled_order() -> None:
    notification = NotificationModel(
        recipient_type="performer",
        type="order_cancelled",
        payload={
            "order_id": "12345678-1234-1234-1234-123456789abc",
            "cancelled_by": "customer",
        },
    )

    text = _notification_text(notification)

    assert "Заказ отменён заказчиком." in text

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from backend.modules.notifications.infrastructure import NotificationModel
from backend.modules.payments.infrastructure import RefundModel
from backend.worker.jobs import (
    DeadlinesWorkerJob,
    NoopWorkerJob,
    NotificationDelivery,
    NotificationWorkerJob,
    RefundWorkerJob,
    _notification_keyboard,
    _notification_text,
)


def _as_notification(value: SimpleNamespace) -> NotificationModel:
    return cast(NotificationModel, value)


class _SessionContext:
    def __init__(self, session: AsyncMock) -> None:
        self.session = session

    async def __aenter__(self) -> AsyncMock:
        return self.session

    async def __aexit__(self, *args: object) -> None:
        return None


def _notification_job(session_factory: Mock | None = None) -> NotificationWorkerJob:
    return NotificationWorkerJob(
        session_factory or Mock(),
        batch_limit=10,
        customer_bot_token=str(uuid4()),
        executor_bot_token=str(uuid4()),
        telegram_api_base_url="http://telegram.test",
        telegram_timeout_seconds=1,
    )


@pytest.mark.unit
async def test_notification_target_resolves_customer_performer_and_invitation() -> None:
    session = AsyncMock()
    result = Mock()
    result.scalar_one_or_none.return_value = 123
    session.execute.return_value = result
    job = _notification_job()

    customer = SimpleNamespace(
        recipient_type="customer",
        customer_id=uuid4(),
        performer_id=None,
        recipient_telegram_id=None,
    )
    performer = SimpleNamespace(
        recipient_type="performer",
        customer_id=None,
        performer_id=uuid4(),
        recipient_telegram_id=None,
    )
    invitation = SimpleNamespace(
        recipient_type="performer_invitation",
        customer_id=None,
        performer_id=None,
        recipient_telegram_id=456,
    )

    assert await job._telegram_target(session, _as_notification(customer)) == (
        job._customer_bot_token,
        123,
    )
    assert await job._telegram_target(session, _as_notification(performer)) == (
        job._executor_bot_token,
        123,
    )
    assert await job._telegram_target(session, _as_notification(invitation)) == (
        job._executor_bot_token,
        456,
    )


@pytest.mark.unit
async def test_notification_target_rejects_missing_telegram_id() -> None:
    session = AsyncMock()
    result = Mock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    job = _notification_job()
    notification = SimpleNamespace(
        recipient_type="customer",
        customer_id=uuid4(),
        performer_id=None,
        recipient_telegram_id=None,
    )

    with pytest.raises(RuntimeError, match="Customer telegram id is missing"):
        await job._telegram_target(session, _as_notification(notification))


@pytest.mark.unit
async def test_notification_target_rejects_missing_performer_telegram_id() -> None:
    session = AsyncMock()
    result = Mock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    job = _notification_job()
    notification = SimpleNamespace(
        recipient_type="performer",
        customer_id=None,
        performer_id=uuid4(),
        recipient_telegram_id=None,
    )

    with pytest.raises(RuntimeError, match="Performer telegram id is missing"):
        await job._telegram_target(session, _as_notification(notification))


@pytest.mark.unit
@pytest.mark.parametrize(
    ("recipient_type", "field", "message"),
    [
        ("customer", "customer_id", "Notification customer is missing"),
        ("performer", "performer_id", "Notification performer is missing"),
        (
            "performer_invitation",
            "recipient_telegram_id",
            "Invitation recipient telegram id is missing",
        ),
    ],
)
async def test_notification_target_rejects_incomplete_recipient(
    recipient_type: str,
    field: str,
    message: str,
) -> None:
    session = AsyncMock()
    notification = SimpleNamespace(
        recipient_type=recipient_type,
        customer_id=uuid4(),
        performer_id=uuid4(),
        recipient_telegram_id=123,
    )
    setattr(notification, field, None)
    job = _notification_job()

    with pytest.raises(RuntimeError, match=message):
        await job._telegram_target(session, _as_notification(notification))


@pytest.mark.unit
@pytest.mark.parametrize(
    ("recipient_type", "kwargs", "message"),
    [
        ("customer", {"customer_id": uuid4()}, "Customer bot token is not configured"),
        (
            "performer",
            {"performer_id": uuid4()},
            "Executor bot token is not configured",
        ),
        (
            "performer_invitation",
            {"recipient_telegram_id": 1},
            "Executor bot token is not configured",
        ),
        ("admin", {}, "Admin Telegram notifications are not configured"),
    ],
)
async def test_notification_target_rejects_unsupported_delivery(
    recipient_type: str,
    kwargs: dict[str, object],
    message: str,
) -> None:
    session = AsyncMock()
    notification = SimpleNamespace(recipient_type=recipient_type, **kwargs)
    job = NotificationWorkerJob(
        Mock(),
        batch_limit=10,
        customer_bot_token="" if recipient_type == "customer" else str(uuid4()),
        executor_bot_token="" if recipient_type != "customer" else str(uuid4()),
        telegram_api_base_url="http://telegram.test",
        telegram_timeout_seconds=1,
    )

    with pytest.raises(RuntimeError, match=message):
        await job._telegram_target(session, _as_notification(notification))


@pytest.mark.unit
async def test_notification_finish_ignores_missing_or_already_finished_row() -> None:
    session = AsyncMock()
    session.get.return_value = None
    job = _notification_job(Mock(return_value=_SessionContext(session)))

    await job._finish(uuid4())
    session.commit.assert_not_awaited()

    session.get.return_value = SimpleNamespace(status="sent")
    await job._finish(uuid4())
    session.commit.assert_not_awaited()


@pytest.mark.unit
async def test_notification_load_delivery_builds_message_payload() -> None:
    session = AsyncMock()
    notification = SimpleNamespace(
        status="processing",
        recipient_type="performer_invitation",
        recipient_telegram_id=42,
        customer_id=None,
        performer_id=None,
        type="performer_invitation_created",
        payload={},
    )
    session.get.return_value = notification
    job = _notification_job(Mock(return_value=_SessionContext(session)))

    delivery = await job._load_delivery(uuid4())

    assert delivery.token
    assert delivery.chat_id == 42
    assert "/start" in delivery.text
    assert delivery.reply_markup is None


@pytest.mark.unit
async def test_notification_load_delivery_enriches_legacy_nearby_payload() -> None:
    order = SimpleNamespace(
        service_name="Уход за питомцем",
        start_at=datetime(2026, 7, 31, 9),
        end_at=datetime(2026, 7, 31, 10),
        objects_count=2,
        total_amount=Decimal("1500.00"),
    )
    notification = SimpleNamespace(
        status="processing",
        recipient_type="performer",
        recipient_telegram_id=None,
        customer_id=None,
        performer_id=uuid4(),
        type="pool_order_available",
        entity_id=uuid4(),
        payload={"order_id": str(uuid4())},
    )
    session = AsyncMock()
    session.get.side_effect = [notification, order]
    target_result = Mock()
    target_result.scalar_one_or_none.return_value = 42
    session.execute.return_value = target_result
    job = _notification_job(Mock(return_value=_SessionContext(session)))

    delivery = await job._load_delivery(uuid4())

    assert "Уход за питомцем" in delivery.text
    assert "Объектов: 2" in delivery.text
    assert "Сумма: 1500.00 ₽" in delivery.text


@pytest.mark.unit
async def test_notification_load_delivery_rejects_unclaimed_row() -> None:
    session = AsyncMock()
    session.get.return_value = None
    job = _notification_job(Mock(return_value=_SessionContext(session)))

    with pytest.raises(RuntimeError, match="Notification is not processing"):
        await job._load_delivery(uuid4())


@pytest.mark.unit
async def test_notification_recovery_and_send_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    factory = Mock(return_value=_SessionContext(session))
    job = _notification_job(factory)

    await job._recover_processing()
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()

    response = Mock()
    response.json.return_value = {"ok": True}

    class _Client:
        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> Mock:
            return response

    monkeypatch.setattr(
        "backend.worker.jobs.httpx.AsyncClient", lambda **kwargs: _Client()
    )
    delivery = cast(
        NotificationDelivery,
        SimpleNamespace(
            token=str(uuid4()),
            chat_id=1,
            text="text",
            reply_markup=None,
        ),
    )
    await job._send_notification(delivery)
    assert delivery.chat_id == 1
    response.raise_for_status.assert_called_once()


@pytest.mark.unit
async def test_refund_claim_batch_builds_gateway_commands() -> None:
    session = AsyncMock()
    refund = cast(
        RefundModel,
        SimpleNamespace(
            id=uuid4(),
            payment_id=uuid4(),
            idempotency_key="refund-key",
            amount=Decimal("10"),
            status="pending",
        ),
    )
    result = Mock()
    result.all.return_value = [(refund, "provider-payment")]
    session.execute.return_value = result
    job = RefundWorkerJob(Mock(return_value=_SessionContext(session)), 10, Mock())

    claimed = await job._claim_batch()

    assert claimed == (
        (
            refund.id,
            refund.payment_id,
            "provider-payment",
            "refund-key",
            Decimal("10"),
        ),
    )
    assert refund.status == "processing"
    session.commit.assert_awaited_once()


@pytest.mark.unit
async def test_refund_worker_marks_success_and_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    factory = Mock(return_value=_SessionContext(session))
    gateway = Mock()
    gateway.create_refund = AsyncMock(
        side_effect=[
            SimpleNamespace(provider_refund_id="provider-refund"),
            RuntimeError("down"),
        ]
    )
    job = RefundWorkerJob(
        factory, batch_limit=10, gateway_factory=Mock(return_value=gateway)
    )
    refund_id = uuid4()
    payment_id = uuid4()
    monkeypatch.setattr(job, "_recover_processing", AsyncMock())
    monkeypatch.setattr(
        job,
        "_claim_batch",
        AsyncMock(
            return_value=(
                (refund_id, payment_id, "provider-payment", "key-1", 10),
                (refund_id, payment_id, "provider-payment", "key-2", 20),
            )
        ),
    )
    mark_succeeded = AsyncMock()
    mark_failed = AsyncMock()
    monkeypatch.setattr(
        "backend.worker.jobs.SqlAlchemyPaymentRepository.mark_refund_succeeded",
        mark_succeeded,
    )
    monkeypatch.setattr(
        "backend.worker.jobs.SqlAlchemyPaymentRepository.mark_refund_failed",
        mark_failed,
    )

    await job.run_once()

    mark_succeeded.assert_awaited_once_with(
        refund_id=refund_id,
        provider_refund_id="provider-refund",
    )
    mark_failed.assert_awaited_once_with(refund_id=refund_id)
    assert session.commit.await_count == 2


@pytest.mark.unit
async def test_notification_finish_marks_sent_and_retries_failed_delivery() -> None:
    notification_id = uuid4()
    session = AsyncMock()
    model = SimpleNamespace(status="processing", attempts=1, sent_at=None)
    session.get.return_value = model
    factory = Mock(return_value=_SessionContext(session))
    job = _notification_job(factory)

    await job._finish(notification_id)
    assert model.status == "sent"
    assert model.sent_at is not None
    session.commit.assert_awaited_once()

    session.commit.reset_mock()
    model.status = "processing"
    model.attempts = 1
    await job._finish(notification_id, error="TimeoutError")
    assert model.status == "pending"
    assert model.last_error == "TimeoutError"
    session.commit.assert_awaited_once()


@pytest.mark.unit
async def test_deadline_helpers_read_settings_and_create_notification() -> None:
    session = Mock()
    session.execute = AsyncMock()
    session.add = Mock()
    result = Mock()
    result.scalar_one_or_none.side_effect = ["15", uuid4(), None]
    session.execute.return_value = result
    job = DeadlinesWorkerJob(Mock(), batch_limit=10)

    assert await job._setting_int(session, "order_approaching_minutes", 60) == 15
    assert await job._first_admin_id(session) is not None
    assert await job._setting_int(session, "missing", 60) == 60

    entity_id = uuid4()
    job._add_notification(
        session=session,
        recipient_type="customer",
        customer_id=uuid4(),
        performer_id=None,
        notification_type="order_started",
        entity_type="order",
        entity_id=entity_id,
        payload={"order_id": str(entity_id)},
        deduplication_key="order-started:test",
    )
    notification = session.add.call_args.args[0]
    assert isinstance(notification, NotificationModel)
    assert notification.status == "pending"
    assert notification.deduplication_key == "order-started:test"


@pytest.mark.unit
async def test_deadline_helper_cancels_pending_entity_notifications() -> None:
    session = Mock()
    session.execute = AsyncMock()
    job = DeadlinesWorkerJob(Mock(), batch_limit=10)

    await job._cancel_pending_notifications(
        session=session,
        entity_type="order",
        entity_id=uuid4(),
    )

    session.execute.assert_awaited_once()


@pytest.mark.unit
async def test_refund_worker_recovers_processing_rows() -> None:
    session = AsyncMock()
    factory = Mock(return_value=_SessionContext(session))
    job = RefundWorkerJob(factory, batch_limit=10, gateway_factory=Mock())

    await job._recover_processing()

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.unit
async def test_notification_claim_batch_marks_pending_rows_processing() -> None:
    session = AsyncMock()
    result = Mock()
    notification_id = uuid4()
    result.scalars.return_value = [notification_id]
    session.execute.return_value = result
    job = _notification_job(Mock(return_value=_SessionContext(session)))

    assert await job._claim_batch() == (notification_id,)
    assert session.execute.await_count == 2
    session.commit.assert_awaited_once()


@pytest.mark.unit
async def test_notification_claim_batch_allows_empty_queue() -> None:
    session = AsyncMock()
    result = Mock()
    result.scalars.return_value = []
    session.execute.return_value = result
    job = _notification_job(Mock(return_value=_SessionContext(session)))

    assert await job._claim_batch() == ()
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.unit
async def test_notification_run_once_finishes_success_and_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = _notification_job()
    recover_processing = AsyncMock()
    claim_batch = AsyncMock(return_value=(uuid4(), uuid4()))
    load_delivery = AsyncMock(side_effect=[object(), RuntimeError("broken")])
    send_notification = AsyncMock()
    finish = AsyncMock()
    monkeypatch.setattr(job, "_recover_processing", recover_processing)
    monkeypatch.setattr(job, "_claim_batch", claim_batch)
    monkeypatch.setattr(job, "_load_delivery", load_delivery)
    monkeypatch.setattr(job, "_send_notification", send_notification)
    monkeypatch.setattr(job, "_finish", finish)

    await job.run_once()

    recover_processing.assert_awaited_once()
    assert send_notification.await_count == 1
    assert finish.await_args_list[0].kwargs == {}
    assert finish.await_args_list[1].kwargs == {"error": "RuntimeError"}


@pytest.mark.unit
async def test_deadline_notification_deduplicates_and_supports_admin_channel() -> None:
    session = Mock()
    session.execute = AsyncMock()
    session.add = Mock()
    result = Mock()
    result.scalar_one_or_none.side_effect = [None, None]
    session.execute.return_value = result
    job = DeadlinesWorkerJob(Mock(), batch_limit=10)
    entity_id = uuid4()

    await job._notify_once(
        session=session,
        recipient_type="admin",
        admin_id=uuid4(),
        notification_type="report_overdue",
        entity_id=entity_id,
        payload={"order_id": str(entity_id)},
        deduplication_key="report-overdue:admin:test",
    )
    await job._notify_once(
        session=session,
        recipient_type="customer",
        customer_id=uuid4(),
        notification_type="report_overdue",
        entity_id=entity_id,
        payload={"order_id": str(entity_id)},
        deduplication_key="report-overdue:customer:test",
    )

    assert session.add.call_count == 2
    admin_notification = session.add.call_args_list[0].args[0]
    assert admin_notification.channel == "admin_panel"
    assert admin_notification.status == "sent"
    notification = session.add.call_args_list[1].args[0]
    assert notification.channel == "telegram"
    assert notification.status == "pending"


@pytest.mark.unit
async def test_deadline_notification_skips_duplicate_and_missing_recipient() -> None:
    session = Mock()
    session.execute = AsyncMock()
    session.add = Mock()
    result = Mock()
    result.scalar_one_or_none.return_value = uuid4()
    session.execute.return_value = result
    job = DeadlinesWorkerJob(Mock(), batch_limit=10)

    await job._notify_once(
        session=session,
        recipient_type="customer",
        customer_id=uuid4(),
        notification_type="order_started",
        entity_id=uuid4(),
        payload={},
        deduplication_key="duplicate",
    )
    job._add_notification(
        session=session,
        recipient_type="customer",
        customer_id=None,
        performer_id=None,
        notification_type="order_started",
        entity_type="order",
        entity_id=uuid4(),
        payload={},
        deduplication_key="missing-recipient",
    )

    session.add.assert_not_called()


@pytest.mark.unit
def test_notification_rendering_covers_performer_and_admin_titles() -> None:
    performer = SimpleNamespace(
        type="order_started",
        recipient_type="performer",
        payload={"order_id": str(uuid4())},
    )
    admin = SimpleNamespace(
        type="order_started",
        recipient_type="admin",
        payload={},
    )

    assert "Исполнитель" in _notification_text(_as_notification(performer))
    assert "Админ" in _notification_text(_as_notification(admin))
    assert _notification_keyboard(_as_notification(performer)) is not None


@pytest.mark.unit
def test_nearby_order_notification_contains_order_details() -> None:
    notification = SimpleNamespace(
        type="pool_order_available",
        recipient_type="performer",
        payload={
            "order_id": str(uuid4()),
            "service_name": "Уход за питомцем",
            "start_at": "2026-07-31T09:00:00+00:00",
            "end_at": "2026-07-31T10:30:00+00:00",
            "objects_count": "2",
            "total_amount": "1500.00",
            "distance_km": "3.25",
            "timezone": "Europe/Moscow",
        },
    )

    text = _notification_text(_as_notification(notification))

    assert "Уход за питомцем" in text
    assert "31.07.2026 12:00 — 13:30" in text
    assert "Объектов: 2" in text
    assert "Сумма: 1500.00 ₽" in text
    assert "Расстояние: 3.25 км" in text


@pytest.mark.unit
def test_direct_invitation_notification_contains_order_details() -> None:
    notification = SimpleNamespace(
        type="direct_invitation_created",
        recipient_type="performer",
        payload={
            "order_id": str(uuid4()),
            "service_name": "Сопровождение",
            "start_at": "2026-07-31T09:00:00+00:00",
            "end_at": "2026-07-31T10:00:00+00:00",
            "objects_count": "1",
            "performer_amount": "800.00",
            "distance_km": "1.75",
            "response_expires_at": "2026-07-30T18:00:00+00:00",
        },
    )

    text = _notification_text(_as_notification(notification))

    assert "Сопровождение" in text
    assert "31.07.2026 09:00 — 10:00" in text
    assert "Объектов: 1" in text
    assert "Ваша сумма: 800.00 ₽" in text
    assert "Расстояние: 1.75 км" in text
    assert "Ответить до: 30.07.2026 18:00" in text


@pytest.mark.unit
async def test_noop_worker_job_is_safe() -> None:
    await NoopWorkerJob().run_once()


@pytest.mark.unit
def test_notification_rendering_handles_invitation_and_role_titles() -> None:
    invitation = SimpleNamespace(
        type="performer_invitation_created",
        recipient_type="performer",
        payload={},
    )
    customer = SimpleNamespace(
        type="order_started",
        recipient_type="customer",
        payload={"order_id": "<order>"},
    )

    assert "/start" in _notification_text(_as_notification(invitation))
    assert "Заказчик" in _notification_text(_as_notification(customer))
    assert "&lt;order&gt;" in _notification_text(_as_notification(customer))
    assert _notification_keyboard(_as_notification(invitation)) is None

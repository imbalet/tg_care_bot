from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from executor_bot.application.dto import AvailableOrderDTO
from executor_bot.presentation.callbacks import NotificationOrderOpenCallback
from executor_bot.presentation.handlers.orders.router import notification_order_callback


def test_handlers_do_not_call_telegram_api_directly() -> None:
    handlers_dir = Path("src/executor_bot/presentation/handlers")
    forbidden = (
        "message.answer(",
        "callback.answer(",
        "callback.message.answer(",
        "send_step(",
        "send_screen(",
    )

    offenders: list[str] = []
    for path in handlers_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden:
            if pattern in text:
                offenders.append(f"{path}:{pattern}")

    assert offenders == []


@pytest.mark.asyncio
async def test_nearby_notification_opens_available_order_card() -> None:
    order_id = uuid4()
    performer_id = uuid4()
    backend = SimpleNamespace(
        get_registration_state=AsyncMock(
            return_value=SimpleNamespace(
                performer=SimpleNamespace(id=performer_id),
            ),
        ),
        list_available_orders=AsyncMock(
            return_value=(
                AvailableOrderDTO(
                    id=order_id,
                    service_name="Уход за питомцем",
                    matching_mode="pool",
                    status="searching",
                    start_at=datetime(2026, 7, 31, 12, tzinfo=UTC),
                    end_at=datetime(2026, 7, 31, 13, tzinfo=UTC),
                    objects_count=1,
                    total_amount=Decimal("1000.00"),
                    distance_km=Decimal("2.5"),
                ),
            ),
        ),
        get_performer_order_card=AsyncMock(),
    )
    responder = AsyncMock()
    viewed_orders = AsyncMock()

    await notification_order_callback(
        callback=object(),
        bot=object(),
        backend_client=backend,
        telegram_responder=responder,
        telegram_user_context=SimpleNamespace(telegram_id=123),
        viewed_available_orders_store=viewed_orders,
        callback_data=NotificationOrderOpenCallback(order_id=str(order_id)),
    )

    backend.get_performer_order_card.assert_not_awaited()
    backend.list_available_orders.assert_awaited_once_with(
        performer_id=performer_id,
    )
    viewed_orders.mark_viewed.assert_awaited_once_with(123, str(order_id))
    assert "Доступный заказ" in responder.update.await_args.kwargs["text"]
    assert "Расстояние: 2.5 км" in responder.update.await_args.kwargs["text"]


@pytest.mark.asyncio
async def test_nearby_notification_shows_stale_action_for_unavailable_order() -> None:
    backend = SimpleNamespace(
        get_registration_state=AsyncMock(
            return_value=SimpleNamespace(performer=SimpleNamespace(id=uuid4())),
        ),
        list_available_orders=AsyncMock(return_value=()),
        get_performer_order_card=AsyncMock(),
    )
    responder = AsyncMock()

    await notification_order_callback(
        callback=object(),
        bot=object(),
        backend_client=backend,
        telegram_responder=responder,
        telegram_user_context=SimpleNamespace(telegram_id=123),
        viewed_available_orders_store=AsyncMock(),
        callback_data=NotificationOrderOpenCallback(order_id=str(uuid4())),
    )

    backend.get_performer_order_card.assert_not_awaited()
    assert "устарел" in responder.update.await_args.kwargs["text"].lower()

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from customer_bot.application.dto import ContactRequestDTO, PerformerProfileDTO
from customer_bot.presentation.callbacks import OrderContactCallback
from customer_bot.presentation.handlers import customer_orders
from customer_bot.presentation.services.performer_profile import show_performer_profile


@pytest.mark.asyncio
async def test_contact_request_refreshes_order_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order_id = uuid4()
    refresh = AsyncMock()
    monkeypatch.setattr(customer_orders, "_show_order_card", refresh)
    backend = AsyncMock()
    backend.create_contact_request.return_value = ContactRequestDTO(
        id=uuid4(),
        order_id=order_id,
        performer_id=uuid4(),
        requested_method="both",
        status="fulfilled",
        failure_reason=None,
        contact_name="Исполнитель",
        contact_phone="+79990000000",
        contact_telegram_username="executor",
    )
    responder = AsyncMock()
    callback = object()
    context = type("Context", (), {"telegram_id": 123})()

    await customer_orders.contact_order_callback(
        callback=callback,
        bot=object(),
        telegram_responder=responder,
        backend_client=backend,
        telegram_user_context=context,
        callback_data=OrderContactCallback(order_id=order_id),
    )

    refresh.assert_awaited_once()
    assert refresh.await_args.kwargs["order_id"] == order_id


@pytest.mark.asyncio
async def test_performer_profile_avatar_uses_photo_replacement() -> None:
    responder = AsyncMock()
    profile = PerformerProfileDTO(
        performer_id=uuid4(),
        full_name="Исполнитель",
        about_text="Опыт",
        city_name="Ростов-на-Дону",
        avatar_url="http://minio:9000/private/avatar.jpg",
        services=(),
    )

    await show_performer_profile(
        bot=object(),
        event=object(),
        telegram_id=123,
        profile=profile,
        telegram_responder=responder,
        back_order_id=uuid4(),
    )

    responder.replace_with_photo.assert_awaited_once()
    assert responder.replace_with_photo.await_args.kwargs["photo"] == profile.avatar_url

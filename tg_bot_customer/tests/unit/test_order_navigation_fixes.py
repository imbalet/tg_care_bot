from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from customer_bot.application.dto import (
    ContactRequestDTO,
    OrderReportDTO,
    OrderReportFileDTO,
    PerformerProfileDTO,
)
from customer_bot.presentation.callbacks import (
    OrderContactCallback,
    OrderReportOpenCallback,
    OrderResponsePerformerProfileCallback,
)
from customer_bot.presentation.handlers import customer_orders
from customer_bot.presentation.handlers.orders import matches
from customer_bot.presentation.handlers.orders import customer_details
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
    backend = AsyncMock()
    backend.download_avatar.return_value = b"avatar"
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
        backend_client=backend,
        telegram_responder=responder,
        back_order_id=uuid4(),
    )

    responder.replace_with_photo.assert_awaited_once()
    photo = responder.replace_with_photo.await_args.kwargs["photo"]
    assert photo.data == b"avatar"


@pytest.mark.asyncio
async def test_response_performer_profile_keeps_responses_order_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order_id = uuid4()
    profile = PerformerProfileDTO(
        performer_id=uuid4(),
        full_name="Исполнитель",
        about_text=None,
        city_name="Ростов-на-Дону",
        avatar_url=None,
        services=(),
    )
    show_profile = AsyncMock()
    monkeypatch.setattr(matches, "show_performer_profile", show_profile)

    state = AsyncMock()
    state.get_data.return_value = {"order_responses_order_id": str(order_id)}
    backend = AsyncMock()
    backend.get_public_performer_profile.return_value = profile
    responder = AsyncMock()

    await matches.response_performer_profile(
        callback=object(),
        bot=object(),
        state=state,
        backend_client=backend,
        telegram_responder=responder,
        telegram_user_context=type("Context", (), {"telegram_id": 123})(),
        callback_data=OrderResponsePerformerProfileCallback(
            performer_id=profile.performer_id,
        ),
    )

    assert show_profile.await_args.kwargs["back_responses_order_id"] == order_id


@pytest.mark.asyncio
async def test_customer_order_report_sends_attachments_as_photos() -> None:
    order_id = uuid4()
    customer_id = uuid4()
    signed_url = "http://minio:9000/report.jpg?signature=secret"
    report = OrderReportDTO(
        id=uuid4(),
        order_id=order_id,
        performer_id=uuid4(),
        completed_work="Работа выполнена",
        comment=None,
        problem_flag=False,
        problem_description=None,
        submitted_at=datetime.now(UTC),
        files=(
            OrderReportFileDTO(
                id=uuid4(),
                original_name="report.jpg",
                mime_type="image/jpeg",
                signed_url=signed_url,
            ),
        ),
    )
    backend = AsyncMock()
    backend.get_customer_profile.return_value = SimpleNamespace(id=customer_id)
    backend.get_customer_order_report.return_value = report
    backend.download_file.return_value = b"photo-bytes"
    responder = AsyncMock()

    await customer_details.open_order_report(
        callback=object(),
        bot=object(),
        backend_client=backend,
        telegram_responder=responder,
        telegram_user_context=SimpleNamespace(telegram_id=123),
        callback_data=OrderReportOpenCallback(order_id=order_id),
    )

    backend.download_file.assert_awaited_once_with(signed_url)
    responder.send_photo.assert_awaited_once()
    photo = responder.send_photo.await_args.kwargs["photo"]
    assert photo.data == b"photo-bytes"
    assert responder.send_photo.await_args.kwargs.get("caption") is None
    assert signed_url not in responder.update.await_args.kwargs["text"]
    assert responder.update.await_args.kwargs["create_new"] is True
    assert [call[0] for call in responder.method_calls] == ["send_photo", "update"]

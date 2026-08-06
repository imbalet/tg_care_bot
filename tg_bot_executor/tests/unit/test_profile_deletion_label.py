from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from executor_bot.presentation.handlers import fallback


@pytest.mark.asyncio
async def test_executor_profile_uses_delete_account_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = SimpleNamespace()
    monkeypatch.setattr(fallback, "Message", type(message))
    performer = SimpleNamespace(
        city_id=uuid4(),
        current_address_id=None,
        avatar_url=None,
        full_name="Исполнитель",
        phone="+79990000000",
        telegram_username=None,
        about_text=None,
        is_accepting_orders=False,
        contact_method="phone",
        status="active",
    )
    backend = AsyncMock()
    backend.get_registration_state.return_value = SimpleNamespace(performer=performer)
    backend.list_active_cities.return_value = ()
    responder = AsyncMock()

    await fallback.profile_callback(
        callback=SimpleNamespace(message=message),
        bot=object(),
        backend_client=backend,
        telegram_responder=responder,
        telegram_user_context=SimpleNamespace(telegram_id=123),
    )

    markup = responder.update.await_args.kwargs["reply_markup"]
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert "Удалить аккаунт" in labels
    assert "Проверить удаление аккаунта" not in labels

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from customer_bot.application.dto import AddressDTO
from customer_bot.presentation.handlers.addresses.completion import (
    _advance_or_create,
)


async def test_address_creation_opens_created_address_card() -> None:
    address = AddressDTO(
        id=uuid4(),
        city_id=uuid4(),
        address_text="Ростов-на-Дону, ул. Тестовая, 1",
        entrance="2",
        floor="3",
        apartment="45",
        comment="Домофон 123",
    )
    backend_client = AsyncMock()
    backend_client.create_address.return_value = address
    state = AsyncMock()
    state.get_data.return_value = {"return_to_order_after_address": False}
    responder = AsyncMock()

    await _advance_or_create(
        event=object(),
        bot=object(),
        state=state,
        backend_client=backend_client,
        telegram_responder=responder,
        telegram_user_context=SimpleNamespace(telegram_id=100),
        draft={
            "city_id": str(address.city_id),
            "unrestricted_value": address.address_text,
            "entrance": address.entrance,
            "floor": address.floor,
            "apartment": address.apartment,
            "comment": address.comment,
            "extra_index": 3,
        },
    )

    backend_client.list_addresses.assert_not_awaited()
    state.clear.assert_awaited_once()
    responder.update.assert_awaited_once()
    update_call = responder.update.await_args.kwargs
    assert address.address_text in update_call["text"]
    assert update_call["reply_markup"] is not None

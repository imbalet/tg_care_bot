from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from customer_bot.application.dto import AddressDTO
from customer_bot.presentation.callbacks import AddressSelectCallback
from customer_bot.presentation.handlers.addresses.list import select_address


async def test_address_selection_reloads_backend_after_stale_fsm_state() -> None:
    address = AddressDTO(
        id=uuid4(),
        city_id=uuid4(),
        address_text="Ростов-на-Дону, ул. Тестовая, 1",
        entrance=None,
        floor=None,
        apartment=None,
        comment=None,
    )
    backend_client = AsyncMock()
    backend_client.list_addresses.return_value = (address,)
    state = AsyncMock()
    state.get_data.return_value = {"addresses": []}
    responder = AsyncMock()

    await select_address(
        callback=object(),
        bot=object(),
        state=state,
        backend_client=backend_client,
        telegram_responder=responder,
        telegram_user_context=SimpleNamespace(telegram_id=100),
        callback_data=AddressSelectCallback(address_id=address.id),
    )

    backend_client.list_addresses.assert_awaited_once_with(telegram_id=100)
    state.update_data.assert_awaited_once()
    update_call = responder.update.await_args.kwargs
    assert address.address_text in update_call["text"]

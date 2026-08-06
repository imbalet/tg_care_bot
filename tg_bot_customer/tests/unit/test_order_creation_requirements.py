from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from customer_bot.application.dto import AddressDTO, CareObjectDTO
from customer_bot.presentation.callbacks import (
    AddressAddCallback,
    CareObjectAddCallback,
)
from customer_bot.presentation.handlers.orders.create import start_order_creation
from customer_bot.presentation.ui.screens.orders.order_no_addresses import (
    Screen as OrderNoAddressesScreen,
)
from customer_bot.presentation.ui.screens.orders.order_requirements import Screen
from customer_bot.presentation.view_models import OrderRequirementsView


def _callback_data(markup: object) -> list[str]:
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data is not None
    ]


def _address() -> AddressDTO:
    return AddressDTO(
        id=uuid4(),
        city_id=uuid4(),
        address_text="Ростов-на-Дону, ул. Тестовая, 1",
        entrance=None,
        floor=None,
        apartment=None,
        comment=None,
    )


def _care_object(object_type: str) -> CareObjectDTO:
    return CareObjectDTO(
        id=uuid4(),
        object_type=object_type,
        display_name="Объект",
        age_group="school",
        species=None,
        breed=None,
        pet_size=None,
        mobility_assistance_required=None,
        routine_notes=None,
        behavior_notes=None,
    )


def test_no_address_order_screen_uses_global_address_creation_callback() -> None:
    result = OrderNoAddressesScreen().build()

    callbacks = _callback_data(result.reply_markup)

    assert callbacks[0] == AddressAddCallback().pack()


@pytest.mark.parametrize(
    ("object_type", "object_label"),
    (("child", "ребенка"), ("ward", "подопечного"), ("pet", "питомца")),
)
def test_requirements_use_the_selected_direction(
    object_type: str,
    object_label: str,
) -> None:
    result = Screen(
        OrderRequirementsView(
            object_type=object_type,
            has_address=True,
            has_care_object=False,
        )
    ).build()

    callbacks = _callback_data(result.reply_markup)

    assert f"добавьте {object_label}" in result.text
    assert CareObjectAddCallback(object_type=object_type).pack() in callbacks
    assert AddressAddCallback().pack() not in callbacks


@pytest.mark.asyncio
async def test_start_order_creation_blocks_without_address_or_matching_object() -> None:
    category = SimpleNamespace(
        code="nanny",
        name="Няня",
        care_object_type="child",
        services=(object(),),
    )
    backend = AsyncMock()
    backend.list_catalog_categories.return_value = (category,)
    backend.list_addresses.return_value = ()
    backend.list_care_objects.return_value = (_care_object("pet"),)
    active_category_store = AsyncMock()
    active_category_store.get.return_value = "nanny"
    state = AsyncMock()
    responder = AsyncMock()

    await start_order_creation(
        callback=object(),
        bot=object(),
        state=state,
        backend_client=backend,
        active_category_store=active_category_store,
        telegram_responder=responder,
        telegram_user_context=SimpleNamespace(telegram_id=123),
    )

    state.clear.assert_awaited_once()
    responder.update.assert_awaited_once()
    screen = responder.update.await_args.kwargs
    assert "адрес и ребенка" in screen["text"]
    callbacks = _callback_data(screen["reply_markup"])
    assert CareObjectAddCallback(object_type="child").pack() in callbacks
    assert AddressAddCallback().pack() in callbacks
    backend.list_care_objects.assert_awaited_once_with(
        telegram_id=123,
        object_type="child",
    )

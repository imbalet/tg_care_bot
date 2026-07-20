import logging

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    OrderAddAddressCallback,
    OrderAddObjectCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.addresses.state import AddressManagement
from customer_bot.presentation.handlers.care_objects.state import CareObjectManagement
from customer_bot.presentation.handlers.orders.state import OrderCreation, draft
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.screens import (
    AddressCityStepScreen,
    CareObjectNameStepScreen,
    RetryLaterScreen,
)
from customer_bot.presentation.view_models import ObjectNameView

router = Router(name="orders_additions")
logger = logging.getLogger(__name__)

CARE_OBJECT_TYPE_LABELS = {
    "child": "Ребенок",
    "ward": "Подопечный",
    "pet": "Питомец",
}


@router.callback_query(OrderCreation.object, OrderAddObjectCallback.filter())
async def add_order_object(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    order_draft = draft(data)
    await state.update_data(
        return_to_order_after_care_object=True,
        draft={"object_type": str(order_draft["care_object_type"])},
        order_draft=order_draft,
    )
    await state.set_state(CareObjectManagement.name)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := CareObjectNameStepScreen(
                ObjectNameView(
                    object_type_label=CARE_OBJECT_TYPE_LABELS.get(
                        str(order_draft["care_object_type"]),
                        "Объект ухода",
                    )
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.callback_query(OrderCreation.address, OrderAddAddressCallback.filter())
async def add_order_address(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        cities = await backend_client.list_active_cities()
    except BackendClientError as exc:
        logger.warning(
            "Failed to load cities for order address creation",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    await state.update_data(
        return_to_order_after_address=True,
        city_ids=[str(city.id) for city in cities],
        city_names=[city.name for city in cities],
        address_draft={},
    )
    await state.set_state(AddressManagement.city)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := AddressCityStepScreen(cities).build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


__all__ = ["router"]

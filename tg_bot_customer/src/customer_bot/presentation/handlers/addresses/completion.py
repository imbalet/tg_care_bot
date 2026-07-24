import logging

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.addresses.state import (
    EXTRA_FIELDS,
    AddressDraftSnapshot,
    extra_index,
)
from customer_bot.presentation.handlers.orders.state import OrderCreation
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.screens import (
    AddressExtraStepScreen,
    AddressListScreen,
    AddressValidationScreen,
    OrderAddressStepScreen,
    RetryLaterScreen,
)
from customer_bot.presentation.view_models import (
    AddressExtraView,
    AddressListItemView,
    AddressListView,
)

logger = logging.getLogger(__name__)


async def _advance_or_create(
    event: Message | CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    draft: dict[str, object],
) -> None:
    snapshot = AddressDraftSnapshot.from_data(draft)
    index = extra_index(draft) + 1
    if index < len(EXTRA_FIELDS):
        draft["extra_index"] = index
        await state.update_data(address_draft=draft)
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text=(
                screen := AddressExtraStepScreen(
                    AddressExtraView(field_name=EXTRA_FIELDS[index][1])
                ).build()
            ).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    try:
        await backend_client.create_address(
            telegram_id=telegram_user_context.telegram_id,
            city_id=snapshot.city_id,
            unrestricted_value=snapshot.unrestricted_value,
            entrance=snapshot.entrance,
            floor=snapshot.floor,
            apartment=snapshot.apartment,
            comment=snapshot.comment,
        )
    except BackendValidationError:
        logger.warning(
            "Backend rejected address creation",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := AddressValidationScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to create address",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    data = await state.get_data()
    if data.get("return_to_order_after_address") is True:
        await _return_to_order_addresses(
            event,
            bot,
            state,
            backend_client,
            telegram_responder,
            telegram_user_context,
        )
        return
    await state.clear()
    logger.info(
        "Address created",
        extra={"telegram_id": telegram_user_context.telegram_id},
    )
    try:
        addresses = await backend_client.list_addresses(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendClientError as exc:
        logger.warning(
            "Address created but failed to reload address list",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text="Адрес сохранен. Откройте список адресов, чтобы увидеть его.",
            reply_markup=None,
            create_new=True,
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := AddressListScreen(
                AddressListView(
                    count=len(addresses),
                    items=tuple(
                        AddressListItemView(
                            id=address.id,
                            address_text=address.address_text,
                        )
                        for address in addresses
                    ),
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


async def _return_to_order_addresses(
    event: Message | CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        addresses = await backend_client.list_addresses(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to reload addresses after order inline creation",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    await state.set_state(OrderCreation.address)
    await state.update_data(
        address_draft={},
        return_to_order_after_address=False,
        order_addresses=[
            {"id": str(address.id), "address_text": address.address_text}
            for address in addresses
        ],
    )
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := OrderAddressStepScreen(addresses).build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )

import logging
from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from customer_bot.application.dto import AddressDTO
from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    AddressDeleteCallback,
    AddressDeleteConfirmCallback,
    AddressesOpenCallback,
    AddressSelectCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.screens import (
    AddressCardScreen,
    AddressDeleteConfirmScreen,
    AddressDeletedScreen,
    AddressListScreen,
    AddressValidationScreen,
    RetryLaterScreen,
    StaleActionScreen,
)
from customer_bot.presentation.view_models import (
    AddressCardView,
    AddressDeleteView,
    AddressListItemView,
    AddressListView,
)

router = Router(name="addresses_list")
logger = logging.getLogger(__name__)


@router.callback_query(AddressesOpenCallback.filter())
async def open_addresses(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        items = await backend_client.list_addresses(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendValidationError:
        logger.warning(
            "Backend rejected address list request",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := AddressValidationScreen().build()).text,
            reply_markup=screen.reply_markup,
        )

        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to load addresses",
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
        )
        return
    await state.update_data(addresses=[_address_state(item) for item in items])
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := AddressListScreen(
                AddressListView(
                    count=len(items),
                    items=tuple(
                        AddressListItemView(
                            id=item.id,
                            address_text=item.address_text,
                        )
                        for item in items
                    ),
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
    )


@router.callback_query(AddressSelectCallback.filter())
async def select_address(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: AddressSelectCallback,
) -> None:
    try:
        addresses = await backend_client.list_addresses(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendValidationError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := AddressValidationScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to reload addresses before selection",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "address_id": str(callback_data.address_id),
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return
    item = next(
        (address for address in addresses if address.id == callback_data.address_id),
        None,
    )
    if item is None:
        logger.warning(
            "Stale address select callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "address_id": str(callback_data.address_id),
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := StaleActionScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return
    await state.update_data(
        addresses=[_address_state(address) for address in addresses]
    )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := AddressCardScreen(
                AddressCardView(
                    id=str(item.id),
                    address_text=item.address_text,
                    entrance=str(item.entrance or ""),
                    floor=str(item.floor or ""),
                    apartment=str(item.apartment or ""),
                    comment=str(item.comment or ""),
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
    )


@router.callback_query(AddressDeleteCallback.filter())
async def delete_address(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: AddressDeleteCallback,
) -> None:
    item = await _address_by_id(state, callback_data.address_id)
    if item is None:
        logger.warning(
            "Stale address delete callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "address_id": str(callback_data.address_id),
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := StaleActionScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := AddressDeleteConfirmScreen(
                AddressDeleteView(id=str(callback_data.address_id))
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
    )


@router.callback_query(AddressDeleteConfirmCallback.filter())
async def confirm_delete_address(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: AddressDeleteConfirmCallback,
) -> None:
    item = await _address_by_id(state, callback_data.address_id)
    if item is None:
        logger.warning(
            "Stale address delete confirm callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "address_id": str(callback_data.address_id),
            },
        )
        await telegram_responder.acknowledge(callback)
        return
    try:
        await backend_client.delete_address(
            telegram_id=telegram_user_context.telegram_id,
            address_id=UUID(str(item["id"])),
        )
    except BackendValidationError:
        logger.warning(
            "Backend rejected address delete",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "address_id": str(item["id"]),
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := AddressValidationScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to delete address",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "address_id": str(item["id"]),
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return
    logger.info(
        "Address deleted",
        extra={
            "telegram_id": telegram_user_context.telegram_id,
            "address_id": str(item["id"]),
        },
    )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := AddressDeletedScreen().build()).text,
        reply_markup=screen.reply_markup,
    )


def _address_state(item: AddressDTO) -> dict[str, object]:
    return {
        "id": str(item.id),
        "city_id": str(item.city_id),
        "address_text": item.address_text,
        "entrance": item.entrance,
        "floor": item.floor,
        "apartment": item.apartment,
        "comment": item.comment,
    }


async def _address_by_id(
    state: FSMContext,
    address_id: UUID,
) -> dict[str, object] | None:
    data = await state.get_data()
    items = data.get("addresses")
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and str(item.get("id")) == str(address_id):
            return dict(item)
    return None

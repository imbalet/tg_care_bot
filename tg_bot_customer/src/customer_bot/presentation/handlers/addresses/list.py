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
    AddressesOpenCallback,
    AddressSelectCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.responses import send_step
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui import (
    address_card_keyboard,
    address_card_text,
    address_deleted_text,
    address_validation_error_text,
    addresses_keyboard,
    addresses_list_text,
    retry_later_text,
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
    except BackendValidationError as exc:
        logger.warning(
            "Backend rejected address list request",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=address_validation_error_text(str(exc)),
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
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await state.update_data(addresses=[_address_state(item) for item in items])
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=addresses_list_text(len(items)),
        reply_markup=addresses_keyboard(items),
    )


@router.callback_query(AddressSelectCallback.filter())
async def select_address(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: AddressSelectCallback,
) -> None:
    item = await _address_by_index(state, callback_data.index)
    if item is None:
        logger.warning(
            "Stale address select callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": callback_data.index,
            },
        )
        return
    index = item["index"]
    if not isinstance(index, int):
        logger.warning(
            "Invalid address index in state",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        return
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=address_card_text(item),
        reply_markup=address_card_keyboard(index),
    )


@router.callback_query(AddressDeleteCallback.filter())
async def delete_address(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: AddressDeleteCallback,
) -> None:
    item = await _address_by_index(state, callback_data.index)
    if item is None:
        logger.warning(
            "Stale address delete callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": callback_data.index,
            },
        )
        return
    try:
        await backend_client.delete_address(
            telegram_id=telegram_user_context.telegram_id,
            address_id=UUID(str(item["id"])),
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to delete address",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "address_id": str(item["id"]),
                "exception_type": type(exc).__name__,
            },
        )
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    logger.info(
        "Address deleted",
        extra={
            "telegram_id": telegram_user_context.telegram_id,
            "address_id": str(item["id"]),
        },
    )
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=address_deleted_text(),
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


async def _address_by_index(
    state: FSMContext,
    index: int,
) -> dict[str, object] | None:
    data = await state.get_data()
    items = data.get("addresses")
    if not isinstance(items, list) or index < 0 or index >= len(items):
        return None
    item = items[index]
    if not isinstance(item, dict):
        return None
    result = dict(item)
    result["index"] = index
    return result

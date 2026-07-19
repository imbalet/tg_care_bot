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
from customer_bot.presentation.ui import (
    address_card_keyboard,
    address_card_text,
    address_delete_confirm_keyboard,
    address_delete_confirm_text,
    address_deleted_text,
    address_validation_error_text,
    addresses_keyboard,
    addresses_list_text,
    delete_blocked_text,
    retry_later_text,
    use_buttons_text,
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
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=address_validation_error_text(str(exc)),
            create_new=True,
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
            text=retry_later_text(),
            create_new=True,
        )
        return
    await state.update_data(addresses=[_address_state(item) for item in items])
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=addresses_list_text(len(items)),
        reply_markup=addresses_keyboard(items),
        create_new=True,
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
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    index = item["index"]
    if not isinstance(index, int):
        logger.warning(
            "Invalid address index in state",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=address_card_text(item),
        reply_markup=address_card_keyboard(index),
        create_new=True,
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
    item = await _address_by_index(state, callback_data.index)
    if item is None:
        logger.warning(
            "Stale address delete callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": callback_data.index,
            },
        )
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=address_delete_confirm_text(),
        reply_markup=address_delete_confirm_keyboard(callback_data.index),
        create_new=True,
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
    item = await _address_by_index(state, callback_data.index)
    if item is None:
        logger.warning(
            "Stale address delete confirm callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": callback_data.index,
            },
        )
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    try:
        await backend_client.delete_address(
            telegram_id=telegram_user_context.telegram_id,
            address_id=UUID(str(item["id"])),
        )
    except BackendValidationError as exc:
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
            text=delete_blocked_text(str(exc)),
            create_new=True,
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
            text=retry_later_text(),
            create_new=True,
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
        text=address_deleted_text(),
        create_new=True,
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

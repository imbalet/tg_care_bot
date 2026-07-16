import logging
from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    AddressAddCallback,
    AddressCityCallback,
    AddressSkipCallback,
    AddressSuggestionCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.addresses.state import (
    EXTRA_FIELDS,
    AddressManagement,
)
from customer_bot.presentation.handlers.addresses.state import (
    address_draft as _draft,
)
from customer_bot.presentation.handlers.addresses.state import (
    extra_index as _extra_index,
)
from customer_bot.presentation.handlers.addresses.state import (
    optional_str as _optional_str,
)
from customer_bot.presentation.handlers.addresses.state import (
    string_list as _string_list,
)
from customer_bot.presentation.handlers.orders.state import OrderCreation
from customer_bot.presentation.handlers.responses import send_step
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui import (
    address_city_keyboard,
    address_city_step_text,
    address_created_text,
    address_extra_step_text,
    address_query_step_text,
    address_skip_keyboard,
    address_suggestion_step_text,
    address_suggestions_keyboard,
    address_validation_error_text,
    order_address_step_text,
    order_addresses_keyboard,
    retry_later_text,
    use_buttons_text,
    validation_error_text,
)

router = Router(name="addresses_create")
logger = logging.getLogger(__name__)


@router.callback_query(AddressAddCallback.filter())
async def add_address(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        cities = await backend_client.list_active_cities()
    except BackendValidationError as exc:
        logger.warning(
            "Backend rejected address creation start",
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
            "Failed to load cities for address creation",
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
    await state.set_state(AddressManagement.city)
    await state.update_data(
        city_ids=[str(city.id) for city in cities],
        city_names=[city.name for city in cities],
        address_draft={},
    )
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=address_city_step_text(),
        reply_markup=address_city_keyboard(cities),
    )


@router.callback_query(AddressManagement.city, AddressCityCallback.filter())
async def select_city(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: AddressCityCallback,
) -> None:
    data = await state.get_data()
    index = callback_data.index
    city_ids = _string_list(data["city_ids"])
    if index < 0 or index >= len(city_ids):
        logger.warning(
            "Invalid address city callback index",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": index,
            },
        )
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    draft = _draft(data)
    draft["city_id"] = city_ids[index]
    await state.update_data(address_draft=draft)
    await state.set_state(AddressManagement.query)
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=address_query_step_text(),
    )


@router.message(AddressManagement.query)
async def enter_query(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text="Введите адрес текстом.",
        )
        return
    data = await state.get_data()
    draft = _draft(data)
    try:
        suggestions = await backend_client.suggest_addresses(
            city_id=UUID(str(draft["city_id"])),
            query=message.text.strip(),
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to suggest addresses",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    if not suggestions:
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text="Адрес не найден. Уточните строку.",
        )
        return
    await state.update_data(
        address_suggestions=[
            {"value": item.value, "unrestricted_value": item.unrestricted_value}
            for item in suggestions
        ],
    )
    await state.set_state(AddressManagement.suggestion)
    await send_step(
        bot=bot,
        event=message,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=address_suggestion_step_text(),
        reply_markup=address_suggestions_keyboard(suggestions),
    )


@router.callback_query(
    AddressManagement.suggestion,
    AddressSuggestionCallback.filter(),
)
async def select_suggestion(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: AddressSuggestionCallback,
) -> None:
    data = await state.get_data()
    suggestions = data.get("address_suggestions")
    index = callback_data.index
    if not isinstance(suggestions, list):
        logger.warning(
            "Address suggestions missing in FSM state",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    if index < 0 or index >= len(suggestions):
        logger.warning(
            "Invalid address suggestion callback index",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": index,
            },
        )
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    suggestion = suggestions[index]
    if not isinstance(suggestion, dict):
        logger.warning(
            "Invalid address suggestion item in FSM state",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    draft = _draft(data)
    draft["unrestricted_value"] = str(suggestion["unrestricted_value"])
    draft["extra_index"] = 0
    await state.update_data(address_draft=draft)
    await state.set_state(AddressManagement.extra)
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=address_extra_step_text(EXTRA_FIELDS[0][1]),
        reply_markup=address_skip_keyboard(),
    )


@router.message(AddressManagement.extra)
async def enter_extra(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    draft = _draft(data)
    index = _extra_index(draft)
    if message.text and message.text.strip():
        draft[EXTRA_FIELDS[index][0]] = message.text.strip()
    await _advance_or_create(
        message,
        bot,
        state,
        backend_client,
        telegram_responder,
        telegram_user_context,
        draft,
    )


@router.callback_query(AddressManagement.extra, AddressSkipCallback.filter())
async def skip_extra(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    await _advance_or_create(
        callback,
        bot,
        state,
        backend_client,
        telegram_responder,
        telegram_user_context,
        _draft(data),
    )


async def _advance_or_create(
    event: Message | CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    draft: dict[str, object],
) -> None:
    index = _extra_index(draft) + 1
    if index < len(EXTRA_FIELDS):
        draft["extra_index"] = index
        await state.update_data(address_draft=draft)
        await send_step(
            bot=bot,
            event=event,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=address_extra_step_text(EXTRA_FIELDS[index][1]),
            reply_markup=address_skip_keyboard(),
        )
        return
    try:
        await backend_client.create_address(
            telegram_id=telegram_user_context.telegram_id,
            city_id=UUID(str(draft["city_id"])),
            unrestricted_value=str(draft["unrestricted_value"]),
            entrance=_optional_str(draft.get("entrance")),
            floor=_optional_str(draft.get("floor")),
            apartment=_optional_str(draft.get("apartment")),
            comment=_optional_str(draft.get("comment")),
        )
    except BackendValidationError as exc:
        logger.warning(
            "Backend rejected address creation",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await send_step(
            bot=bot,
            event=event,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=validation_error_text(str(exc)),
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
        await send_step(
            bot=bot,
            event=event,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
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
    await send_step(
        bot=bot,
        event=event,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=address_created_text(),
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
        await send_step(
            bot=bot,
            event=event,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
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
    await send_step(
        bot=bot,
        event=event,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_address_step_text(),
        reply_markup=order_addresses_keyboard(addresses),
    )

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
from customer_bot.presentation.handlers.addresses.completion import (
    _advance_or_create,
)
from customer_bot.presentation.handlers.addresses.state import (
    EXTRA_FIELDS,
    AddressManagement,
    address_draft,
    extra_index,
    string_list,
)
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.screens import (
    AddressCityStepScreen,
    AddressExtraStepScreen,
    AddressQueryStepScreen,
    AddressSuggestionScreen,
    AddressValidationScreen,
    RetryLaterScreen,
)
from customer_bot.presentation.view_models import AddressExtraView

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
    except BackendValidationError:
        logger.warning(
            "Backend rejected address creation start",
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
            "Failed to load cities for address creation",
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
    await state.set_state(AddressManagement.city)
    await state.update_data(
        city_ids=[str(city.id) for city in cities],
        city_names=[city.name for city in cities],
        address_draft={},
    )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := AddressCityStepScreen(cities).build()).text,
        reply_markup=screen.reply_markup,
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
    city_id = callback_data.city_id
    city_ids = string_list(data["city_ids"])
    if str(city_id) not in city_ids:
        logger.warning(
            "Invalid address city callback index",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "city_id": str(city_id),
            },
        )
        await telegram_responder.acknowledge(callback)
        return
    draft = address_draft(data)
    draft["city_id"] = str(city_id)
    await state.update_data(address_draft=draft)
    await state.set_state(AddressManagement.query)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := AddressQueryStepScreen().build()).text,
        reply_markup=screen.reply_markup,
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
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := AddressQueryStepScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    data = await state.get_data()
    draft = address_draft(data)
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
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    if not suggestions:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := AddressQueryStepScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    await state.update_data(
        address_suggestions=[
            {"value": item.value, "unrestricted_value": item.unrestricted_value}
            for item in suggestions
        ],
    )
    await state.set_state(AddressManagement.suggestion)
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := AddressSuggestionScreen(suggestions).build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
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
        await telegram_responder.acknowledge(callback)
        return
    if index < 0 or index >= len(suggestions):
        logger.warning(
            "Invalid address suggestion callback index",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": index,
            },
        )
        await telegram_responder.acknowledge(callback)
        return
    suggestion = suggestions[index]
    if not isinstance(suggestion, dict):
        logger.warning(
            "Invalid address suggestion item in FSM state",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.acknowledge(callback)
        return
    draft = address_draft(data)
    draft["unrestricted_value"] = str(suggestion["unrestricted_value"])
    draft["extra_index"] = 0
    await state.update_data(address_draft=draft)
    await state.set_state(AddressManagement.extra)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := AddressExtraStepScreen(
                AddressExtraView(field_name=EXTRA_FIELDS[0][1])
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
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
    draft = address_draft(data)
    index = extra_index(draft)
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
        address_draft(data),
    )

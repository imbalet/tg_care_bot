from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from customer_bot.application.dto import AddressDTO
from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    AddressAddCallback,
    AddressCityCallback,
    AddressDeleteCallback,
    AddressesOpenCallback,
    AddressSelectCallback,
    AddressSkipCallback,
    AddressSuggestionCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.responses import send_step
from customer_bot.presentation.services import MenuManager
from customer_bot.presentation.ui import (
    address_card_keyboard,
    address_card_text,
    address_city_keyboard,
    address_city_step_text,
    address_created_text,
    address_deleted_text,
    address_extra_step_text,
    address_query_step_text,
    address_skip_keyboard,
    address_suggestion_step_text,
    address_suggestions_keyboard,
    address_validation_error_text,
    addresses_keyboard,
    addresses_list_text,
    retry_later_text,
)

router = Router(name="addresses")

EXTRA_FIELDS = (
    ("entrance", "Подъезд"),
    ("floor", "Этаж"),
    ("apartment", "Квартира"),
    ("comment", "Комментарий"),
)


class AddressManagement(StatesGroup):
    city = State()
    query = State()
    suggestion = State()
    extra = State()


@router.callback_query(AddressesOpenCallback.filter())
async def open_addresses(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        items = await backend_client.list_addresses(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendValidationError as exc:
        await send_step(
            bot=bot,
            event=callback,
            menu_manager=menu_manager,
            telegram_user_context=telegram_user_context,
            text=address_validation_error_text(str(exc)),
        )
        return
    except BackendClientError:
        await send_step(
            bot=bot,
            event=callback,
            menu_manager=menu_manager,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await state.update_data(addresses=[_address_state(item) for item in items])
    await send_step(
        bot=bot,
        event=callback,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=addresses_list_text(len(items)),
        reply_markup=addresses_keyboard(items),
    )


@router.callback_query(AddressAddCallback.filter())
async def add_address(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        cities = await backend_client.list_active_cities()
    except BackendValidationError as exc:
        await send_step(
            bot=bot,
            event=callback,
            menu_manager=menu_manager,
            telegram_user_context=telegram_user_context,
            text=address_validation_error_text(str(exc)),
        )
        return
    except BackendClientError:
        await send_step(
            bot=bot,
            event=callback,
            menu_manager=menu_manager,
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
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=address_city_step_text(),
        reply_markup=address_city_keyboard(cities),
    )


@router.callback_query(AddressManagement.city, AddressCityCallback.filter())
async def select_city(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
    callback_data: AddressCityCallback,
) -> None:
    data = await state.get_data()
    index = callback_data.index
    city_ids = _string_list(data["city_ids"])
    if index < 0 or index >= len(city_ids):
        return
    draft = _draft(data)
    draft["city_id"] = city_ids[index]
    await state.update_data(address_draft=draft)
    await state.set_state(AddressManagement.query)
    await send_step(
        bot=bot,
        event=callback,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=address_query_step_text(),
    )


@router.message(AddressManagement.query)
async def enter_query(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await send_step(
            bot=bot,
            event=message,
            menu_manager=menu_manager,
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
    except BackendClientError:
        await send_step(
            bot=bot,
            event=message,
            menu_manager=menu_manager,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    if not suggestions:
        await send_step(
            bot=bot,
            event=message,
            menu_manager=menu_manager,
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
        menu_manager=menu_manager,
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
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
    callback_data: AddressSuggestionCallback,
) -> None:
    data = await state.get_data()
    suggestions = data.get("address_suggestions")
    index = callback_data.index
    if not isinstance(suggestions, list):
        return
    if index < 0 or index >= len(suggestions):
        return
    suggestion = suggestions[index]
    if not isinstance(suggestion, dict):
        return
    draft = _draft(data)
    draft["unrestricted_value"] = str(suggestion["unrestricted_value"])
    draft["extra_index"] = 0
    await state.update_data(address_draft=draft)
    await state.set_state(AddressManagement.extra)
    await send_step(
        bot=bot,
        event=callback,
        menu_manager=menu_manager,
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
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    draft = _draft(data)
    index = _extra_index(draft)
    if message.text and message.text.strip():
        draft[EXTRA_FIELDS[index][0]] = message.text.strip()
    await _advance_or_create(
        message, bot, state, backend_client, menu_manager, telegram_user_context, draft
    )


@router.callback_query(AddressManagement.extra, AddressSkipCallback.filter())
async def skip_extra(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    await _advance_or_create(
        callback,
        bot,
        state,
        backend_client,
        menu_manager,
        telegram_user_context,
        _draft(data),
    )


@router.callback_query(AddressSelectCallback.filter())
async def select_address(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
    callback_data: AddressSelectCallback,
) -> None:
    item = await _address_by_index(state, callback_data.index)
    if item is None:
        return
    index = item["index"]
    if not isinstance(index, int):
        return
    await send_step(
        bot=bot,
        event=callback,
        menu_manager=menu_manager,
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
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
    callback_data: AddressDeleteCallback,
) -> None:
    item = await _address_by_index(state, callback_data.index)
    if item is None:
        return
    try:
        await backend_client.delete_address(
            telegram_id=telegram_user_context.telegram_id,
            address_id=UUID(str(item["id"])),
        )
    except BackendClientError:
        await send_step(
            bot=bot,
            event=callback,
            menu_manager=menu_manager,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await send_step(
        bot=bot,
        event=callback,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=address_deleted_text(),
    )


async def _advance_or_create(
    event: Message | CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    menu_manager: MenuManager,
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
            menu_manager=menu_manager,
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
    except BackendClientError:
        await send_step(
            bot=bot,
            event=event,
            menu_manager=menu_manager,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await state.clear()
    await send_step(
        bot=bot,
        event=event,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=address_created_text(),
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


def _draft(data: dict[str, object]) -> dict[str, object]:
    draft = data.get("address_draft")
    if isinstance(draft, dict):
        return dict(draft)
    raise TypeError("Expected address draft in FSM state")


def _string_list(value: object) -> list[str]:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise TypeError("Expected string list in FSM state")


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _extra_index(draft: dict[str, object]) -> int:
    value = draft.get("extra_index", 0)
    return value if isinstance(value, int) else 0

from uuid import UUID

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from customer_bot.infrastructure.http import (
    AddressDTO,
    BackendClient,
    BackendClientError,
    BackendValidationError,
)
from customer_bot.presentation.contexts import TelegramUserContext
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
from customer_bot.presentation.ui.keyboards import (
    ADDRESS_ADD,
    ADDRESS_CITY_PREFIX,
    ADDRESS_DELETE_PREFIX,
    ADDRESS_SELECT_PREFIX,
    ADDRESS_SKIP,
    ADDRESS_SUGGESTION_PREFIX,
    ADDRESSES_OPEN,
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


@router.callback_query(F.data == ADDRESSES_OPEN)
async def open_addresses(
    callback: CallbackQuery,
    state: FSMContext,
    backend_client: BackendClient,
    telegram_user_context: TelegramUserContext,
) -> None:
    await callback.answer()
    message = _callback_message(callback)
    if message is None:
        return
    try:
        items = await backend_client.list_addresses(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendValidationError as exc:
        await message.answer(address_validation_error_text(str(exc)))
        return
    except BackendClientError:
        await message.answer(retry_later_text())
        return
    await state.update_data(addresses=[_address_state(item) for item in items])
    await message.answer(
        addresses_list_text(len(items)),
        reply_markup=addresses_keyboard(items),
    )


@router.callback_query(F.data == ADDRESS_ADD)
async def add_address(
    callback: CallbackQuery,
    state: FSMContext,
    backend_client: BackendClient,
) -> None:
    await callback.answer()
    message = _callback_message(callback)
    if message is None:
        return
    try:
        cities = await backend_client.list_active_cities()
    except BackendValidationError as exc:
        await message.answer(address_validation_error_text(str(exc)))
        return
    except BackendClientError:
        await message.answer(retry_later_text())
        return
    await state.set_state(AddressManagement.city)
    await state.update_data(
        city_ids=[str(city.id) for city in cities],
        city_names=[city.name for city in cities],
        address_draft={},
    )
    await message.answer(
        address_city_step_text(), reply_markup=address_city_keyboard(cities)
    )


@router.callback_query(AddressManagement.city, F.data.startswith(ADDRESS_CITY_PREFIX))
async def select_city(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    message = _callback_message(callback)
    data = await state.get_data()
    index = _callback_index(callback.data, ADDRESS_CITY_PREFIX)
    city_ids = _string_list(data["city_ids"])
    if message is None or index is None or index >= len(city_ids):
        return
    draft = _draft(data)
    draft["city_id"] = city_ids[index]
    await state.update_data(address_draft=draft)
    await state.set_state(AddressManagement.query)
    await message.answer(address_query_step_text())


@router.message(AddressManagement.query)
async def enter_query(
    message: Message,
    state: FSMContext,
    backend_client: BackendClient,
) -> None:
    if not message.text or not message.text.strip():
        await message.answer("Введите адрес текстом.")
        return
    data = await state.get_data()
    draft = _draft(data)
    try:
        suggestions = await backend_client.suggest_addresses(
            city_id=UUID(str(draft["city_id"])),
            query=message.text.strip(),
        )
    except BackendClientError:
        await message.answer(retry_later_text())
        return
    if not suggestions:
        await message.answer("Адрес не найден. Уточните строку.")
        return
    await state.update_data(
        address_suggestions=[
            {"value": item.value, "unrestricted_value": item.unrestricted_value}
            for item in suggestions
        ],
    )
    await state.set_state(AddressManagement.suggestion)
    await message.answer(
        address_suggestion_step_text(),
        reply_markup=address_suggestions_keyboard(suggestions),
    )


@router.callback_query(
    AddressManagement.suggestion,
    F.data.startswith(ADDRESS_SUGGESTION_PREFIX),
)
async def select_suggestion(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    message = _callback_message(callback)
    data = await state.get_data()
    suggestions = data.get("address_suggestions")
    index = _callback_index(callback.data, ADDRESS_SUGGESTION_PREFIX)
    if message is None or index is None or not isinstance(suggestions, list):
        return
    if index >= len(suggestions):
        return
    suggestion = suggestions[index]
    if not isinstance(suggestion, dict):
        return
    draft = _draft(data)
    draft["unrestricted_value"] = str(suggestion["unrestricted_value"])
    draft["extra_index"] = 0
    await state.update_data(address_draft=draft)
    await state.set_state(AddressManagement.extra)
    await message.answer(
        address_extra_step_text(EXTRA_FIELDS[0][1]),
        reply_markup=address_skip_keyboard(),
    )


@router.message(AddressManagement.extra)
async def enter_extra(
    message: Message,
    state: FSMContext,
    backend_client: BackendClient,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    draft = _draft(data)
    index = _extra_index(draft)
    if message.text and message.text.strip():
        draft[EXTRA_FIELDS[index][0]] = message.text.strip()
    await _advance_or_create(
        message, state, backend_client, telegram_user_context, draft
    )


@router.callback_query(AddressManagement.extra, F.data == ADDRESS_SKIP)
async def skip_extra(
    callback: CallbackQuery,
    state: FSMContext,
    backend_client: BackendClient,
    telegram_user_context: TelegramUserContext,
) -> None:
    await callback.answer()
    message = _callback_message(callback)
    if message is None:
        return
    data = await state.get_data()
    await _advance_or_create(
        message,
        state,
        backend_client,
        telegram_user_context,
        _draft(data),
    )


@router.callback_query(F.data.startswith(ADDRESS_SELECT_PREFIX))
async def select_address(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    message = _callback_message(callback)
    item = await _address_from_callback(callback, state, ADDRESS_SELECT_PREFIX)
    if message is None or item is None:
        return
    index = item["index"]
    if not isinstance(index, int):
        return
    await message.answer(
        address_card_text(item), reply_markup=address_card_keyboard(index)
    )


@router.callback_query(F.data.startswith(ADDRESS_DELETE_PREFIX))
async def delete_address(
    callback: CallbackQuery,
    state: FSMContext,
    backend_client: BackendClient,
    telegram_user_context: TelegramUserContext,
) -> None:
    await callback.answer()
    message = _callback_message(callback)
    item = await _address_from_callback(callback, state, ADDRESS_DELETE_PREFIX)
    if message is None or item is None:
        return
    try:
        await backend_client.delete_address(
            telegram_id=telegram_user_context.telegram_id,
            address_id=UUID(str(item["id"])),
        )
    except BackendClientError:
        await message.answer(retry_later_text())
        return
    await message.answer(address_deleted_text())


async def _advance_or_create(
    message: Message,
    state: FSMContext,
    backend_client: BackendClient,
    telegram_user_context: TelegramUserContext,
    draft: dict[str, object],
) -> None:
    index = _extra_index(draft) + 1
    if index < len(EXTRA_FIELDS):
        draft["extra_index"] = index
        await state.update_data(address_draft=draft)
        await message.answer(
            address_extra_step_text(EXTRA_FIELDS[index][1]),
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
        await message.answer(retry_later_text())
        return
    await state.clear()
    await message.answer(address_created_text())


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


async def _address_from_callback(
    callback: CallbackQuery,
    state: FSMContext,
    prefix: str,
) -> dict[str, object] | None:
    index = _callback_index(callback.data, prefix)
    data = await state.get_data()
    items = data.get("addresses")
    if index is None or not isinstance(items, list) or index >= len(items):
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


def _callback_index(data: str | None, prefix: str) -> int | None:
    value = _callback_value(data, prefix)
    if value is None or not value.isdigit():
        return None
    return int(value)


def _callback_value(data: str | None, prefix: str) -> str | None:
    if data is None or not data.startswith(prefix):
        return None
    return data.removeprefix(prefix)


def _callback_message(callback: CallbackQuery) -> Message | None:
    return callback.message if isinstance(callback.message, Message) else None


def _string_list(value: object) -> list[str]:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise TypeError("Expected string list in FSM state")


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _extra_index(draft: dict[str, object]) -> int:
    value = draft.get("extra_index", 0)
    return value if isinstance(value, int) else 0

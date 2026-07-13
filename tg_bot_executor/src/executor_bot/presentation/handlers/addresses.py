from uuid import UUID

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from executor_bot.infrastructure.http import (
    AddressDTO,
    BackendClient,
    BackendClientError,
    BackendValidationError,
)
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.ui import (
    retry_later_text,
    work_address_card_keyboard,
    work_address_card_text,
    work_address_city_keyboard,
    work_address_city_step_text,
    work_address_created_text,
    work_address_current_text,
    work_address_deleted_text,
    work_address_extra_step_text,
    work_address_query_step_text,
    work_address_skip_keyboard,
    work_address_suggestion_step_text,
    work_address_suggestions_keyboard,
    work_address_validation_error_text,
    work_addresses_keyboard,
    work_addresses_list_text,
)
from executor_bot.presentation.ui.keyboards import (
    WORK_ADDRESS_ADD,
    WORK_ADDRESS_CITY_PREFIX,
    WORK_ADDRESS_CURRENT_PREFIX,
    WORK_ADDRESS_DELETE_PREFIX,
    WORK_ADDRESS_SELECT_PREFIX,
    WORK_ADDRESS_SKIP,
    WORK_ADDRESS_SUGGESTION_PREFIX,
    WORK_ADDRESSES_OPEN,
)

router = Router(name="work_addresses")

EXTRA_FIELDS = (
    ("entrance", "Подъезд"),
    ("floor", "Этаж"),
    ("apartment", "Квартира"),
    ("comment", "Комментарий"),
)


class WorkAddressManagement(StatesGroup):
    city = State()
    query = State()
    suggestion = State()
    extra = State()


@router.callback_query(F.data == WORK_ADDRESSES_OPEN)
async def open_work_addresses(
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
        items = await backend_client.list_work_addresses(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendValidationError as exc:
        await message.answer(work_address_validation_error_text(str(exc)))
        return
    except BackendClientError:
        await message.answer(retry_later_text())
        return
    await state.update_data(work_addresses=[_address_state(item) for item in items])
    await message.answer(
        work_addresses_list_text(len(items)),
        reply_markup=work_addresses_keyboard(items),
    )


@router.callback_query(F.data == WORK_ADDRESS_ADD)
async def add_work_address(
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
        await message.answer(work_address_validation_error_text(str(exc)))
        return
    except BackendClientError:
        await message.answer(retry_later_text())
        return
    await state.set_state(WorkAddressManagement.city)
    await state.update_data(
        city_ids=[str(city.id) for city in cities],
        work_address_draft={},
    )
    await message.answer(
        work_address_city_step_text(),
        reply_markup=work_address_city_keyboard(cities),
    )


@router.callback_query(
    WorkAddressManagement.city,
    F.data.startswith(WORK_ADDRESS_CITY_PREFIX),
)
async def select_city(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    message = _callback_message(callback)
    data = await state.get_data()
    index = _callback_index(callback.data, WORK_ADDRESS_CITY_PREFIX)
    city_ids = _string_list(data["city_ids"])
    if message is None or index is None or index >= len(city_ids):
        return
    draft = _draft(data)
    draft["city_id"] = city_ids[index]
    await state.update_data(work_address_draft=draft)
    await state.set_state(WorkAddressManagement.query)
    await message.answer(work_address_query_step_text())


@router.message(WorkAddressManagement.query)
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
        work_address_suggestions=[
            {"value": item.value, "unrestricted_value": item.unrestricted_value}
            for item in suggestions
        ],
    )
    await state.set_state(WorkAddressManagement.suggestion)
    await message.answer(
        work_address_suggestion_step_text(),
        reply_markup=work_address_suggestions_keyboard(suggestions),
    )


@router.callback_query(
    WorkAddressManagement.suggestion,
    F.data.startswith(WORK_ADDRESS_SUGGESTION_PREFIX),
)
async def select_suggestion(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    message = _callback_message(callback)
    data = await state.get_data()
    suggestions = data.get("work_address_suggestions")
    index = _callback_index(callback.data, WORK_ADDRESS_SUGGESTION_PREFIX)
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
    await state.update_data(work_address_draft=draft)
    await state.set_state(WorkAddressManagement.extra)
    await message.answer(
        work_address_extra_step_text(EXTRA_FIELDS[0][1]),
        reply_markup=work_address_skip_keyboard(),
    )


@router.message(WorkAddressManagement.extra)
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


@router.callback_query(WorkAddressManagement.extra, F.data == WORK_ADDRESS_SKIP)
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


@router.callback_query(F.data.startswith(WORK_ADDRESS_SELECT_PREFIX))
async def select_address(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    message = _callback_message(callback)
    item = await _address_from_callback(callback, state, WORK_ADDRESS_SELECT_PREFIX)
    if message is None or item is None:
        return
    index = item["index"]
    if not isinstance(index, int):
        return
    await message.answer(
        work_address_card_text(item),
        reply_markup=work_address_card_keyboard(index),
    )


@router.callback_query(F.data.startswith(WORK_ADDRESS_CURRENT_PREFIX))
async def set_current_address(
    callback: CallbackQuery,
    state: FSMContext,
    backend_client: BackendClient,
    telegram_user_context: TelegramUserContext,
) -> None:
    await callback.answer()
    message = _callback_message(callback)
    item = await _address_from_callback(callback, state, WORK_ADDRESS_CURRENT_PREFIX)
    if message is None or item is None:
        return
    try:
        await backend_client.set_current_work_address(
            telegram_id=telegram_user_context.telegram_id,
            address_id=UUID(str(item["id"])),
        )
    except BackendClientError:
        await message.answer(retry_later_text())
        return
    await message.answer(work_address_current_text())


@router.callback_query(F.data.startswith(WORK_ADDRESS_DELETE_PREFIX))
async def delete_address(
    callback: CallbackQuery,
    state: FSMContext,
    backend_client: BackendClient,
    telegram_user_context: TelegramUserContext,
) -> None:
    await callback.answer()
    message = _callback_message(callback)
    item = await _address_from_callback(callback, state, WORK_ADDRESS_DELETE_PREFIX)
    if message is None or item is None:
        return
    try:
        await backend_client.delete_work_address(
            telegram_id=telegram_user_context.telegram_id,
            address_id=UUID(str(item["id"])),
        )
    except BackendClientError:
        await message.answer(retry_later_text())
        return
    await message.answer(work_address_deleted_text())


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
        await state.update_data(work_address_draft=draft)
        await message.answer(
            work_address_extra_step_text(EXTRA_FIELDS[index][1]),
            reply_markup=work_address_skip_keyboard(),
        )
        return
    try:
        await backend_client.create_work_address(
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
    await message.answer(work_address_created_text())


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
    items = data.get("work_addresses")
    if index is None or not isinstance(items, list) or index >= len(items):
        return None
    item = items[index]
    if not isinstance(item, dict):
        return None
    result = dict(item)
    result["index"] = index
    return result


def _draft(data: dict[str, object]) -> dict[str, object]:
    draft = data.get("work_address_draft")
    if isinstance(draft, dict):
        return dict(draft)
    raise TypeError("Expected work address draft in FSM state")


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


__all__ = ["WorkAddressManagement", "router"]

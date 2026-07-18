from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from executor_bot.application.dto import AddressDTO
from executor_bot.application.errors import BackendClientError, BackendValidationError
from executor_bot.application.ports import BackendPort
from executor_bot.presentation.callbacks import (
    WorkAddressAddCallback,
    WorkAddressCityCallback,
    WorkAddressCurrentCallback,
    WorkAddressDeleteCallback,
    WorkAddressesOpenCallback,
    WorkAddressSelectCallback,
    WorkAddressSkipCallback,
    WorkAddressSuggestionCallback,
)
from executor_bot.presentation.handlers.responses import send_step
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.services import TelegramResponder
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


@router.callback_query(WorkAddressesOpenCallback.filter())
async def open_work_addresses(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        items = await backend_client.list_work_addresses(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendValidationError as exc:
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=work_address_validation_error_text(str(exc)),
        )
        return
    except BackendClientError:
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await state.update_data(work_addresses=[_address_state(item) for item in items])
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=work_addresses_list_text(len(items)),
        reply_markup=work_addresses_keyboard(items),
    )


@router.callback_query(WorkAddressAddCallback.filter())
async def add_work_address(
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
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=work_address_validation_error_text(str(exc)),
        )
        return
    except BackendClientError:
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await state.set_state(WorkAddressManagement.city)
    await state.update_data(
        city_ids=[str(city.id) for city in cities],
        work_address_draft={},
    )
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=work_address_city_step_text(),
        reply_markup=work_address_city_keyboard(cities),
    )


@router.callback_query(
    WorkAddressManagement.city,
    WorkAddressCityCallback.filter(),
)
async def select_city(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: WorkAddressCityCallback,
) -> None:
    data = await state.get_data()
    index = callback_data.index
    city_ids = _string_list(data["city_ids"])
    if index < 0 or index >= len(city_ids):
        return
    draft = _draft(data)
    draft["city_id"] = city_ids[index]
    await state.update_data(work_address_draft=draft)
    await state.set_state(WorkAddressManagement.query)
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=work_address_query_step_text(),
    )


@router.message(WorkAddressManagement.query)
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
    except BackendClientError:
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
        work_address_suggestions=[
            {"value": item.value, "unrestricted_value": item.unrestricted_value}
            for item in suggestions
        ],
    )
    await state.set_state(WorkAddressManagement.suggestion)
    await send_step(
        bot=bot,
        event=message,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=work_address_suggestion_step_text(),
        reply_markup=work_address_suggestions_keyboard(suggestions),
    )


@router.callback_query(
    WorkAddressManagement.suggestion,
    WorkAddressSuggestionCallback.filter(),
)
async def select_suggestion(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: WorkAddressSuggestionCallback,
) -> None:
    data = await state.get_data()
    suggestions = data.get("work_address_suggestions")
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
    await state.update_data(work_address_draft=draft)
    await state.set_state(WorkAddressManagement.extra)
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=work_address_extra_step_text(EXTRA_FIELDS[0][1]),
        reply_markup=work_address_skip_keyboard(),
    )


@router.message(WorkAddressManagement.extra)
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


@router.callback_query(WorkAddressManagement.extra, WorkAddressSkipCallback.filter())
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


@router.callback_query(WorkAddressSelectCallback.filter())
async def select_address(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: WorkAddressSelectCallback,
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
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=work_address_card_text(item),
        reply_markup=work_address_card_keyboard(index),
    )


@router.callback_query(WorkAddressCurrentCallback.filter())
async def set_current_address(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: WorkAddressCurrentCallback,
) -> None:
    item = await _address_by_index(state, callback_data.index)
    if item is None:
        return
    try:
        await backend_client.set_current_work_address(
            telegram_id=telegram_user_context.telegram_id,
            address_id=UUID(str(item["id"])),
        )
    except BackendClientError:
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=work_address_current_text(),
    )


@router.callback_query(WorkAddressDeleteCallback.filter())
async def delete_address(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: WorkAddressDeleteCallback,
) -> None:
    item = await _address_by_index(state, callback_data.index)
    if item is None:
        return
    try:
        await backend_client.delete_work_address(
            telegram_id=telegram_user_context.telegram_id,
            address_id=UUID(str(item["id"])),
        )
    except BackendClientError:
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=work_address_deleted_text(),
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
        await state.update_data(work_address_draft=draft)
        await send_step(
            bot=bot,
            event=event,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=work_address_extra_step_text(EXTRA_FIELDS[index][1]),
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
        await send_step(
            bot=bot,
            event=event,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await state.clear()
    await send_step(
        bot=bot,
        event=event,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=work_address_created_text(),
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
    items = data.get("work_addresses")
    if not isinstance(items, list) or index < 0 or index >= len(items):
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

from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from customer_bot.application.dto import CareObjectDTO
from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import ActiveCategoryStore, BackendPort
from customer_bot.presentation.callbacks import (
    CareObjectAddCallback,
    CareObjectAgeCallback,
    CareObjectDeleteCallback,
    CareObjectEditCallback,
    CareObjectMobilityCallback,
    CareObjectSelectCallback,
    CareObjectSizeCallback,
    CareObjectSkipCallback,
    CareObjectsOpenCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.responses import send_step
from customer_bot.presentation.navigation import (
    active_category,
    category_by_code,
    list_categories,
)
from customer_bot.presentation.services import MenuManager
from customer_bot.presentation.ui import (
    care_object_age_keyboard,
    care_object_age_step_text,
    care_object_breed_step_text,
    care_object_card_keyboard,
    care_object_card_text,
    care_object_created_text,
    care_object_deleted_text,
    care_object_mobility_keyboard,
    care_object_mobility_step_text,
    care_object_name_step_text,
    care_object_notes_step_text,
    care_object_size_keyboard,
    care_object_size_step_text,
    care_object_skip_keyboard,
    care_object_species_step_text,
    care_objects_keyboard,
    care_objects_list_text,
    retry_later_text,
    use_buttons_text,
)
from customer_bot.presentation.ui.keyboards import CARE_OBJECT_TYPE_LABELS

router = Router(name="care_objects")


class CareObjectManagement(StatesGroup):
    name = State()
    age = State()
    species = State()
    breed = State()
    size = State()
    mobility = State()
    notes = State()
    edit_name = State()


@router.callback_query(CareObjectsOpenCallback.filter())
async def open_care_objects(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    active_category_store: ActiveCategoryStore,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectsOpenCallback,
) -> None:
    try:
        if callback_data.category_code is not None:
            categories = await list_categories(backend_client)
            category = category_by_code(categories, callback_data.category_code)
        else:
            category = await active_category(
                backend_client=backend_client,
                active_category_store=active_category_store,
                telegram_id=telegram_user_context.telegram_id,
            )
        object_type = category.care_object_type if category is not None else None
        items = await backend_client.list_care_objects(
            telegram_id=telegram_user_context.telegram_id,
            object_type=object_type,
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
    await state.update_data(care_objects=[_care_object_state(item) for item in items])
    await send_step(
        bot=bot,
        event=callback,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=care_objects_list_text(len(items), category),
        reply_markup=care_objects_keyboard(items, object_type=object_type),
    )


@router.callback_query(CareObjectSelectCallback.filter())
async def select_care_object(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectSelectCallback,
) -> None:
    item = await _care_object_by_index(state, callback_data.index)
    if item is None:
        await send_step(
            bot=bot,
            event=callback,
            menu_manager=menu_manager,
            telegram_user_context=telegram_user_context,
            text=use_buttons_text(),
        )
        return
    index = item["index"]
    if not isinstance(index, int):
        return
    await send_step(
        bot=bot,
        event=callback,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=care_object_card_text(item),
        reply_markup=care_object_card_keyboard(index),
    )


@router.callback_query(CareObjectAddCallback.filter())
async def add_care_object(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectAddCallback,
) -> None:
    object_type = callback_data.object_type
    if object_type not in CARE_OBJECT_TYPE_LABELS:
        return
    await state.set_state(CareObjectManagement.name)
    await state.update_data(draft={"object_type": object_type})
    await send_step(
        bot=bot,
        event=callback,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=care_object_name_step_text(CARE_OBJECT_TYPE_LABELS[object_type]),
    )


@router.message(CareObjectManagement.name)
async def enter_name(
    message: Message,
    bot: Bot,
    state: FSMContext,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await send_step(
            bot=bot,
            event=message,
            menu_manager=menu_manager,
            telegram_user_context=telegram_user_context,
            text="Введите имя текстом.",
        )
        return
    data = await state.get_data()
    draft = _draft(data)
    draft["display_name"] = message.text.strip()
    await state.update_data(draft=draft)
    await state.set_state(CareObjectManagement.age)
    await send_step(
        bot=bot,
        event=message,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=care_object_age_step_text(),
        reply_markup=care_object_age_keyboard(str(draft["object_type"])),
    )


@router.callback_query(
    CareObjectManagement.age,
    CareObjectAgeCallback.filter(),
)
async def enter_age(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectAgeCallback,
) -> None:
    age_group = callback_data.age_group
    data = await state.get_data()
    draft = _draft(data)
    draft["age_group"] = age_group
    await state.update_data(draft=draft)
    object_type = str(draft["object_type"])
    if object_type == "pet":
        await state.set_state(CareObjectManagement.species)
        await send_step(
            bot=bot,
            event=callback,
            menu_manager=menu_manager,
            telegram_user_context=telegram_user_context,
            text=care_object_species_step_text(),
        )
        return
    if object_type == "ward":
        await state.set_state(CareObjectManagement.mobility)
        await send_step(
            bot=bot,
            event=callback,
            menu_manager=menu_manager,
            telegram_user_context=telegram_user_context,
            text=care_object_mobility_step_text(),
            reply_markup=care_object_mobility_keyboard(),
        )
        return
    await state.set_state(CareObjectManagement.notes)
    await send_step(
        bot=bot,
        event=callback,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=care_object_notes_step_text(),
        reply_markup=care_object_skip_keyboard(),
    )


@router.message(CareObjectManagement.species)
async def enter_species(
    message: Message,
    bot: Bot,
    state: FSMContext,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await send_step(
            bot=bot,
            event=message,
            menu_manager=menu_manager,
            telegram_user_context=telegram_user_context,
            text="Введите вид питомца текстом.",
        )
        return
    data = await state.get_data()
    draft = _draft(data)
    draft["species"] = message.text.strip()
    await state.update_data(draft=draft)
    await state.set_state(CareObjectManagement.breed)
    await send_step(
        bot=bot,
        event=message,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=care_object_breed_step_text(),
        reply_markup=care_object_skip_keyboard(),
    )


@router.message(CareObjectManagement.breed)
async def enter_breed(
    message: Message,
    bot: Bot,
    state: FSMContext,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    draft = _draft(data)
    if message.text and message.text.strip():
        draft["breed"] = message.text.strip()
    await state.update_data(draft=draft)
    await state.set_state(CareObjectManagement.size)
    await send_step(
        bot=bot,
        event=message,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=care_object_size_step_text(),
        reply_markup=care_object_size_keyboard(),
    )


@router.callback_query(CareObjectManagement.breed, CareObjectSkipCallback.filter())
async def skip_breed(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.set_state(CareObjectManagement.size)
    await send_step(
        bot=bot,
        event=callback,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=care_object_size_step_text(),
        reply_markup=care_object_size_keyboard(),
    )


@router.callback_query(
    CareObjectManagement.size,
    CareObjectSizeCallback.filter(),
)
async def enter_size(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectSizeCallback,
) -> None:
    size = callback_data.size
    data = await state.get_data()
    draft = _draft(data)
    draft["pet_size"] = size
    await state.update_data(draft=draft)
    await state.set_state(CareObjectManagement.notes)
    await send_step(
        bot=bot,
        event=callback,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=care_object_notes_step_text(),
        reply_markup=care_object_skip_keyboard(),
    )


@router.callback_query(
    CareObjectManagement.mobility,
    CareObjectMobilityCallback.filter(),
)
async def enter_mobility(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectMobilityCallback,
) -> None:
    value = callback_data.value
    data = await state.get_data()
    draft = _draft(data)
    draft["mobility_assistance_required"] = value == "yes"
    await state.update_data(draft=draft)
    await state.set_state(CareObjectManagement.notes)
    await send_step(
        bot=bot,
        event=callback,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=care_object_notes_step_text(),
        reply_markup=care_object_skip_keyboard(),
    )


@router.message(CareObjectManagement.notes)
async def enter_notes(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    draft = _draft(data)
    if message.text and message.text.strip():
        draft["routine_notes"] = message.text.strip()
    await _create_from_draft(
        message, bot, state, backend_client, menu_manager, telegram_user_context, draft
    )


@router.callback_query(CareObjectManagement.notes, CareObjectSkipCallback.filter())
async def skip_notes(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    await _create_from_draft(
        callback,
        bot,
        state,
        backend_client,
        menu_manager,
        telegram_user_context,
        _draft(data),
    )


@router.callback_query(CareObjectEditCallback.filter())
async def edit_care_object(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectEditCallback,
) -> None:
    item = await _care_object_by_index(state, callback_data.index)
    if item is None:
        return
    await state.update_data(edit_item=item)
    await state.set_state(CareObjectManagement.edit_name)
    await send_step(
        bot=bot,
        event=callback,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text="Введите новое имя карточки.",
    )


@router.message(CareObjectManagement.edit_name)
async def enter_edit_name(
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
            text="Введите имя текстом.",
        )
        return
    data = await state.get_data()
    item = _state_item(data["edit_item"])
    try:
        await backend_client.update_care_object(
            telegram_id=telegram_user_context.telegram_id,
            care_object_id=UUID(str(item["id"])),
            display_name=message.text.strip(),
            age_group=str(item["age_group"]),
            species=_optional_str(item.get("species")),
            breed=_optional_str(item.get("breed")),
            pet_size=_optional_str(item.get("pet_size")),
            mobility_assistance_required=_optional_bool(
                item.get("mobility_assistance_required"),
            ),
            routine_notes=_optional_str(item.get("routine_notes")),
            behavior_notes=_optional_str(item.get("behavior_notes")),
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
    await state.clear()
    await send_step(
        bot=bot,
        event=message,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        text=care_object_created_text(),
    )


@router.callback_query(CareObjectDeleteCallback.filter())
async def delete_care_object(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectDeleteCallback,
) -> None:
    item = await _care_object_by_index(state, callback_data.index)
    if item is None:
        return
    try:
        await backend_client.delete_care_object(
            telegram_id=telegram_user_context.telegram_id,
            care_object_id=UUID(str(item["id"])),
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
        text=care_object_deleted_text(),
    )


async def _create_from_draft(
    event: Message | CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
    draft: dict[str, object],
) -> None:
    try:
        await backend_client.create_care_object(
            telegram_id=telegram_user_context.telegram_id,
            object_type=str(draft["object_type"]),
            display_name=str(draft["display_name"]),
            age_group=str(draft["age_group"]),
            species=_optional_str(draft.get("species")),
            breed=_optional_str(draft.get("breed")),
            pet_size=_optional_str(draft.get("pet_size")),
            mobility_assistance_required=_optional_bool(
                draft.get("mobility_assistance_required"),
            ),
            routine_notes=_optional_str(draft.get("routine_notes")),
            behavior_notes=_optional_str(draft.get("behavior_notes")),
        )
    except BackendValidationError:
        await send_step(
            bot=bot,
            event=event,
            menu_manager=menu_manager,
            telegram_user_context=telegram_user_context,
            text="Backend отклонил данные карточки. Начните заново.",
        )
        await state.clear()
        return
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
        text=care_object_created_text(),
    )


def _care_object_state(item: CareObjectDTO) -> dict[str, object]:
    return {
        "id": str(item.id),
        "object_type": item.object_type,
        "display_name": item.display_name,
        "age_group": item.age_group,
        "species": item.species,
        "breed": item.breed,
        "pet_size": item.pet_size,
        "mobility_assistance_required": item.mobility_assistance_required,
        "routine_notes": item.routine_notes,
        "behavior_notes": item.behavior_notes,
    }


async def _care_object_by_index(
    state: FSMContext,
    index: int,
) -> dict[str, object] | None:
    data = await state.get_data()
    items = data.get("care_objects")
    if not isinstance(items, list):
        return None
    if index < 0 or index >= len(items):
        return None
    item = _state_item(items[index])
    item["index"] = index
    return item


def _draft(data: dict[str, object]) -> dict[str, object]:
    draft = data.get("draft")
    if isinstance(draft, dict):
        return dict(draft)
    raise TypeError("Expected care object draft in FSM state")


def _state_item(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    raise TypeError("Expected care object item in FSM state")


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None

from dataclasses import dataclass
from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from customer_bot.infrastructure.http import (
    BackendClient,
    BackendClientError,
    BackendValidationError,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.services import MenuManager, TelegramTopicSetupService
from customer_bot.presentation.ui import (
    backend_rejected_registration_text,
    contact_methods_keyboard,
    customer_main_menu_text,
    full_name_step_text,
    invalid_text_input_text,
    legal_acceptance_keyboard,
    legal_documents_text,
    main_menu_keyboard,
    phone_step_text,
    registration_complete_text,
    registration_summary_keyboard,
    registration_unavailable_text,
    retry_later_text,
    select_city_keyboard,
    select_city_text,
    select_contact_method_text,
    summary_text,
    use_buttons_text,
)
from customer_bot.presentation.ui.keyboards import (
    REGISTRATION_ACCEPT_LEGAL,
    REGISTRATION_CITY_PREFIX,
    REGISTRATION_CONFIRM,
    REGISTRATION_CONTACT_PREFIX,
    REGISTRATION_EDIT,
)

router = Router(name="registration")

CONTACT_METHOD_LABELS = {
    "telegram": "Telegram",
    "phone": "Телефон",
    "both": "Telegram и телефон",
}


@dataclass(frozen=True)
class _CityView:
    name: str


class CustomerRegistration(StatesGroup):
    legal_acceptance = State()
    full_name = State()
    phone = State()
    city = State()
    contact_method = State()
    summary = State()


async def start_registration(
    message: Message,
    state: FSMContext,
    backend_client: BackendClient,
) -> None:
    try:
        cities = await backend_client.list_active_cities()
        documents = await backend_client.list_active_legal_documents()
    except BackendClientError:
        await message.answer(retry_later_text())
        return
    await state.set_state(CustomerRegistration.legal_acceptance)
    await state.update_data(
        city_ids=[str(city.id) for city in cities],
        city_names=[city.name for city in cities],
        legal_document_ids=[str(document.id) for document in documents],
    )
    await message.answer(
        legal_documents_text(documents),
        reply_markup=legal_acceptance_keyboard(documents),
    )


@router.callback_query(
    CustomerRegistration.legal_acceptance,
    F.data == REGISTRATION_ACCEPT_LEGAL,
)
async def accept_legal(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(CustomerRegistration.full_name)
    message = _callback_message(callback)
    if message is not None:
        await message.answer(full_name_step_text())


@router.message(CustomerRegistration.legal_acceptance)
async def reject_legal(message: Message) -> None:
    await message.answer(use_buttons_text(), reply_markup=legal_acceptance_keyboard())


@router.message(CustomerRegistration.full_name)
async def enter_full_name(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip():
        await message.answer(invalid_text_input_text("Введите ФИО текстом."))
        return
    await state.update_data(full_name=message.text.strip())
    await state.set_state(CustomerRegistration.phone)
    await message.answer(phone_step_text())


@router.message(CustomerRegistration.phone)
async def enter_phone(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip():
        await message.answer("Введите телефон текстом.")
        return
    data = await state.get_data()
    await state.update_data(phone=message.text.strip())
    await state.set_state(CustomerRegistration.city)
    await message.answer(
        select_city_text(),
        reply_markup=select_city_keyboard(_cities_from_state(data)),
    )


@router.callback_query(
    CustomerRegistration.city,
    F.data.startswith(REGISTRATION_CITY_PREFIX),
)
async def enter_city(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    city_ids = _string_list(data["city_ids"])
    city_index = _callback_index(callback.data, REGISTRATION_CITY_PREFIX)
    if city_index is None or city_index < 0 or city_index >= len(city_ids):
        message = _callback_message(callback)
        if message is not None:
            await message.answer(
                registration_unavailable_text(),
                reply_markup=select_city_keyboard(_cities_from_state(data)),
            )
        return
    city_id = city_ids[city_index]
    await state.update_data(
        city_id=city_id,
        city_name=_string_list(data["city_names"])[city_index],
    )
    await state.set_state(CustomerRegistration.contact_method)
    message = _callback_message(callback)
    if message is not None:
        await message.answer(
            select_contact_method_text(),
            reply_markup=contact_methods_keyboard(),
        )


@router.message(CustomerRegistration.city)
async def unknown_city_action(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await message.answer(
        use_buttons_text(),
        reply_markup=select_city_keyboard(_cities_from_state(data)),
    )


@router.callback_query(
    CustomerRegistration.contact_method,
    F.data.startswith(REGISTRATION_CONTACT_PREFIX),
)
async def enter_contact_method(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    contact_method = _callback_value(callback.data, REGISTRATION_CONTACT_PREFIX)
    if contact_method is None:
        message = _callback_message(callback)
        if message is not None:
            await message.answer(
                use_buttons_text(),
                reply_markup=contact_methods_keyboard(),
            )
        return
    label = CONTACT_METHOD_LABELS.get(contact_method)
    if label is None:
        message = _callback_message(callback)
        if message is not None:
            await message.answer(
                use_buttons_text(),
                reply_markup=contact_methods_keyboard(),
            )
        return
    await state.update_data(contact_method=contact_method, contact_method_label=label)
    data = await state.get_data()
    await state.set_state(CustomerRegistration.summary)
    message = _callback_message(callback)
    if message is not None:
        await message.answer(
            summary_text(data),
            reply_markup=registration_summary_keyboard(),
        )


@router.message(CustomerRegistration.contact_method)
async def unknown_contact_method_action(message: Message) -> None:
    await message.answer(use_buttons_text(), reply_markup=contact_methods_keyboard())


@router.callback_query(CustomerRegistration.summary, F.data == REGISTRATION_EDIT)
async def edit_registration(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(CustomerRegistration.full_name)
    message = _callback_message(callback)
    if message is not None:
        await message.answer(full_name_step_text())


@router.callback_query(CustomerRegistration.summary, F.data == REGISTRATION_CONFIRM)
async def confirm_registration(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendClient,
    menu_manager: MenuManager,
    topic_setup_service: TelegramTopicSetupService,
    telegram_user_context: TelegramUserContext,
) -> None:
    await callback.answer()
    data = await state.get_data()
    message = _callback_message(callback)
    try:
        await backend_client.register_customer(
            telegram_id=telegram_user_context.telegram_id,
            full_name=str(data["full_name"]),
            phone=str(data["phone"]),
            city_id=UUID(str(data["city_id"])),
            contact_method=str(data["contact_method"]),
            telegram_username=telegram_user_context.username,
            accepted_legal_document_ids=tuple(
                UUID(document_id)
                for document_id in _string_list(data["legal_document_ids"])
            ),
        )
        if telegram_user_context.chat_id is not None:
            await topic_setup_service.ensure(
                bot=bot,
                backend_client=backend_client,
                telegram_id=telegram_user_context.telegram_id,
                chat_id=telegram_user_context.chat_id,
            )
    except BackendValidationError:
        if message is not None:
            await message.answer(backend_rejected_registration_text())
        await state.clear()
        return
    except BackendClientError:
        if message is not None:
            await message.answer(retry_later_text())
        return
    await state.clear()
    if message is not None:
        await message.answer(registration_complete_text())
        topic_key = await menu_manager.topic_key(
            telegram_id=telegram_user_context.telegram_id,
            message_thread_id=telegram_user_context.message_thread_id,
        )
        await menu_manager.send_or_replace(
            bot=bot,
            message=message,
            telegram_id=telegram_user_context.telegram_id,
            topic_key=topic_key,
            text=customer_main_menu_text(topic_key),
            reply_markup=main_menu_keyboard(topic_key),
            message_thread_id=telegram_user_context.message_thread_id,
        )


@router.message(CustomerRegistration.summary)
async def unknown_summary_action(message: Message) -> None:
    await message.answer(
        use_buttons_text(),
        reply_markup=registration_summary_keyboard(),
    )


def _cities_from_state(data: dict[str, object]) -> tuple[_CityView, ...]:
    return tuple(_CityView(name) for name in _string_list(data["city_names"]))


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

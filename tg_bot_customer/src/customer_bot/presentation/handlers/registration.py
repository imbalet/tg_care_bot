import logging
from dataclasses import dataclass
from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    RegistrationCityCallback,
    RegistrationConfirmCallback,
    RegistrationContactCallback,
    RegistrationEditCallback,
    RegistrationLegalAcceptCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.navigation import show_category_select
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.types import ContactMethod
from customer_bot.presentation.ui import (
    backend_rejected_registration_text,
    contact_methods_keyboard,
    full_name_step_text,
    invalid_phone_contact_text,
    invalid_text_input_text,
    legal_acceptance_keyboard,
    legal_documents_text,
    phone_contact_keyboard,
    phone_contact_received_text,
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
    wrong_phone_contact_text,
)

router = Router(name="registration")
logger = logging.getLogger(__name__)

CONTACT_METHOD_LABELS: dict[ContactMethod, str] = {
    ContactMethod.TELEGRAM: "Telegram",
    ContactMethod.PHONE: "Телефон",
    ContactMethod.BOTH: "Telegram и телефон",
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
    backend_client: BackendPort,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        cities = await backend_client.list_active_cities()
        documents = await backend_client.list_active_legal_documents()
    except BackendClientError as exc:
        logger.warning(
            "Failed to load registration prerequisites",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
            create_new=True,
        )
        return
    await state.set_state(CustomerRegistration.legal_acceptance)
    await state.update_data(
        city_ids=[str(city.id) for city in cities],
        city_names=[city.name for city in cities],
        legal_document_ids=[str(document.id) for document in documents],
    )
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=legal_documents_text(documents),
        reply_markup=legal_acceptance_keyboard(documents),
        create_new=True,
    )


@router.callback_query(
    CustomerRegistration.legal_acceptance,
    RegistrationLegalAcceptCallback.filter(),
)
async def accept_legal(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.set_state(CustomerRegistration.full_name)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=full_name_step_text(),
        create_new=True,
    )


@router.message(CustomerRegistration.legal_acceptance)
async def reject_legal(
    message: Message,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=use_buttons_text(),
        reply_markup=legal_acceptance_keyboard(),
        create_new=True,
    )


@router.message(CustomerRegistration.full_name)
async def enter_full_name(
    message: Message,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=invalid_text_input_text("Введите ФИО текстом."),
            create_new=True,
        )
        return
    await state.update_data(full_name=message.text.strip())
    await state.set_state(CustomerRegistration.phone)
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=phone_step_text(),
        reply_markup=phone_contact_keyboard(),
        create_new=True,
    )


@router.message(CustomerRegistration.phone)
async def enter_phone(
    message: Message,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if message.contact is None:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=invalid_phone_contact_text(),
            reply_markup=phone_contact_keyboard(),
            create_new=True,
        )
        return
    if (
        message.contact.user_id is not None
        and message.contact.user_id != telegram_user_context.telegram_id
    ):
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=wrong_phone_contact_text(),
            reply_markup=phone_contact_keyboard(),
            create_new=True,
        )
        return
    data = await state.get_data()
    await state.update_data(phone=message.contact.phone_number)
    await state.set_state(CustomerRegistration.city)
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=phone_contact_received_text(),
        reply_markup=ReplyKeyboardRemove(),
        create_new=True,
    )
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=select_city_text(),
        reply_markup=select_city_keyboard(_cities_from_state(data)),
        create_new=True,
    )


@router.callback_query(
    CustomerRegistration.city,
    RegistrationCityCallback.filter(),
)
async def enter_city(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: RegistrationCityCallback,
) -> None:
    data = await state.get_data()
    city_ids = _string_list(data["city_ids"])
    city_index = callback_data.index
    if city_index < 0 or city_index >= len(city_ids):
        logger.warning(
            "Invalid registration city callback index",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": city_index,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=registration_unavailable_text(),
            reply_markup=select_city_keyboard(_cities_from_state(data)),
            create_new=True,
        )
        return
    city_id = city_ids[city_index]
    await state.update_data(
        city_id=city_id,
        city_name=_string_list(data["city_names"])[city_index],
    )
    await state.set_state(CustomerRegistration.contact_method)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=select_contact_method_text(),
        reply_markup=contact_methods_keyboard(),
        create_new=True,
    )


@router.message(CustomerRegistration.city)
async def unknown_city_action(
    message: Message,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=use_buttons_text(),
        reply_markup=select_city_keyboard(_cities_from_state(data)),
        create_new=True,
    )


@router.callback_query(
    CustomerRegistration.contact_method,
    RegistrationContactCallback.filter(),
)
async def enter_contact_method(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: RegistrationContactCallback,
) -> None:
    contact_method = callback_data.method
    label = CONTACT_METHOD_LABELS.get(contact_method)
    if label is None:
        logger.warning(
            "Invalid registration contact method callback",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=use_buttons_text(),
            reply_markup=contact_methods_keyboard(),
            create_new=True,
        )
        return
    await state.update_data(contact_method=contact_method, contact_method_label=label)
    data = await state.get_data()
    await state.set_state(CustomerRegistration.summary)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=summary_text(data),
        reply_markup=registration_summary_keyboard(),
        create_new=True,
    )


@router.message(CustomerRegistration.contact_method)
async def unknown_contact_method_action(
    message: Message,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=use_buttons_text(),
        reply_markup=contact_methods_keyboard(),
        create_new=True,
    )


@router.callback_query(CustomerRegistration.summary, RegistrationEditCallback.filter())
async def edit_registration(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.set_state(CustomerRegistration.full_name)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=full_name_step_text(),
        create_new=True,
    )


@router.callback_query(
    CustomerRegistration.summary,
    RegistrationConfirmCallback.filter(),
)
async def confirm_registration(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
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
    except BackendValidationError:
        logger.warning(
            "Backend rejected customer registration",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=backend_rejected_registration_text(),
            create_new=True,
        )
        await state.clear()
        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to register customer",
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
    await state.clear()
    logger.info(
        "Customer registration completed",
        extra={"telegram_id": telegram_user_context.telegram_id},
    )
    await telegram_responder.send_notice(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=registration_complete_text(),
    )
    await show_category_select(
        bot=bot,
        event=callback,
        telegram_user_context=telegram_user_context,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        force_create_new=True,
    )


@router.message(CustomerRegistration.summary)
async def unknown_summary_action(
    message: Message,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=use_buttons_text(),
        reply_markup=registration_summary_keyboard(),
        create_new=True,
    )


def _cities_from_state(data: dict[str, object]) -> tuple[_CityView, ...]:
    return tuple(_CityView(name) for name in _string_list(data["city_names"]))


def _string_list(value: object) -> list[str]:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise TypeError("Expected string list in FSM state")

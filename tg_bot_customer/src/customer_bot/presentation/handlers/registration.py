import logging
from collections.abc import Mapping, Sequence
from dataclasses import replace
from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

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
from customer_bot.presentation.handlers.registration_state import (
    CustomerRegistration,
    _RegistrationCity,
    _RegistrationData,
    _RegistrationLegalDocument,
)
from customer_bot.presentation.navigation import show_category_select
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.types import ContactMethod
from customer_bot.presentation.ui.screens import (
    BackendRejectedRegistrationScreen,
    DocumentsScreen,
    FullNameStepScreen,
    InvalidTextInputScreen,
    PhoneStepScreen,
    RegistrationCompleteScreen,
    RegistrationUnavailableScreen,
    RetryLaterScreen,
    SelectCityScreen,
    SelectContactMethodScreen,
    SummaryScreen,
    WrongPhoneContactScreen,
)

router = Router(name="registration")
logger = logging.getLogger(__name__)


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
        screen = RetryLaterScreen().build()
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=screen.text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return

    registration = _RegistrationData(
        cities=tuple(
            _RegistrationCity(
                id=str(city.id),
                name=city.name,
            )
            for city in cities
        ),
        legal_documents=tuple(
            _RegistrationLegalDocument(
                id=str(document.id),
                document_type=document.document_type,
                version=document.version,
                content_url=document.content_url,
            )
            for document in documents
        ),
    )

    await state.set_state(CustomerRegistration.legal_acceptance)
    await state.set_data(registration.to_state_data())

    screen = DocumentsScreen(registration.legal_documents).build()
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
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

    screen = FullNameStepScreen().build()
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.message(CustomerRegistration.legal_acceptance)
async def reject_legal(
    message: Message,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    registration = await _get_registration_data(state)

    screen = DocumentsScreen(registration.legal_documents).build()
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
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
    full_name = message.text.strip() if message.text else ""
    if not full_name:
        screen = InvalidTextInputScreen("Введите ФИО текстом.").build()
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=screen.text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return

    registration = replace(
        await _get_registration_data(state),
        full_name=full_name,
    )
    await _set_registration_data(state, registration)
    await state.set_state(CustomerRegistration.phone)

    screen = PhoneStepScreen().build()
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
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
    contact = message.contact
    if contact is None:
        screen = PhoneStepScreen().build()
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=screen.text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return

    if (
        contact.user_id is not None
        and contact.user_id != telegram_user_context.telegram_id
    ):
        screen = WrongPhoneContactScreen().build()
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=screen.text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return

    registration = replace(
        await _get_registration_data(state),
        phone=contact.phone_number,
    )
    await _set_registration_data(state, registration)
    await state.set_state(CustomerRegistration.city)

    screen = SelectCityScreen(registration.cities).build()
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
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
    registration = await _get_registration_data(state)
    city = registration.city_by_id(callback_data.city_id)

    if city is None:
        logger.warning(
            "Invalid registration city callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "city_id": str(callback_data.city_id),
            },
        )
        screen = RegistrationUnavailableScreen().build()
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=screen.text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return

    registration = replace(
        registration,
        city_id=city.id,
        city_name=city.name,
    )
    await _set_registration_data(state, registration)
    await state.set_state(CustomerRegistration.contact_method)

    screen = SelectContactMethodScreen().build()
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
    )


@router.message(CustomerRegistration.city)
async def unknown_city_action(
    message: Message,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    registration = await _get_registration_data(state)

    screen = SelectCityScreen(registration.cities).build()
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
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

    try:
        _contact_method_label(contact_method)
    except ValueError:
        logger.warning(
            "Invalid registration contact method callback",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        screen = SelectContactMethodScreen().build()
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=screen.text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return

    registration = replace(
        await _get_registration_data(state),
        contact_method=contact_method,
    )
    await _set_registration_data(state, registration)
    await state.set_state(CustomerRegistration.summary)

    screen = SummaryScreen(registration.summary_view()).build()
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
    )


@router.message(CustomerRegistration.contact_method)
async def unknown_contact_method_action(
    message: Message,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    screen = SelectContactMethodScreen().build()
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
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

    screen = FullNameStepScreen().build()
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
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
    registration = await _get_registration_data(state)

    try:
        await backend_client.register_customer(
            telegram_id=telegram_user_context.telegram_id,
            full_name=_required(registration.full_name, "full_name"),
            phone=_required(registration.phone, "phone"),
            city_id=UUID(_required(registration.city_id, "city_id")),
            contact_method=_required(
                registration.contact_method,
                "contact_method",
            ).value,
            telegram_username=telegram_user_context.username,
            accepted_legal_document_ids=tuple(
                UUID(document.id) for document in registration.legal_documents
            ),
        )
    except BackendValidationError:
        logger.warning(
            "Backend rejected customer registration",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        screen = BackendRejectedRegistrationScreen().build()
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=screen.text,
            reply_markup=screen.reply_markup,
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
        screen = RetryLaterScreen().build()
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=screen.text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return

    await state.clear()
    logger.info(
        "Customer registration completed",
        extra={"telegram_id": telegram_user_context.telegram_id},
    )

    screen = RegistrationCompleteScreen().build()
    await telegram_responder.send_notice(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
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
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    registration = await _get_registration_data(state)

    screen = SummaryScreen(registration.summary_view()).build()
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


async def _get_registration_data(state: FSMContext) -> _RegistrationData:
    return _RegistrationData.from_state(await state.get_data())


async def _set_registration_data(
    state: FSMContext,
    registration: _RegistrationData,
) -> None:
    await state.set_data(registration.to_state_data())


def _contact_method_label(contact_method: ContactMethod) -> str:
    match contact_method:
        case ContactMethod.TELEGRAM:
            return "Telegram"
        case ContactMethod.PHONE:
            return "Телефон"
        case ContactMethod.BOTH:
            return "Telegram и телефон"
        case _:
            raise ValueError(f"Unsupported contact method: {contact_method!r}")


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected {name} mapping in FSM state")
    return value


def _sequence(value: object, name: str) -> Sequence[object]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"Expected {name} sequence in FSM state")
    return value


def _required_str(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise TypeError(f"Expected {key} string in FSM state")
    return value


def _optional_str(value: object, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"Expected {name} string in FSM state")
    return value


def _required[T](value: T | None, name: str) -> T:
    if value is None:
        raise TypeError(f"Missing required registration field: {name}")
    return value

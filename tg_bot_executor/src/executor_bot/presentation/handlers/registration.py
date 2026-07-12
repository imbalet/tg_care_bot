from uuid import UUID

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from executor_bot.application.registration import (
    CONTACT_METHODS,
    format_cities,
    format_contact_methods,
    format_legal_documents,
    parse_city_choice,
)
from executor_bot.infrastructure.http import (
    BackendClient,
    BackendClientError,
    BackendValidationError,
)
from executor_bot.presentation.middlewares import TelegramUserContext

router = Router(name="registration")


class ExecutorRegistration(StatesGroup):
    legal_acceptance = State()
    full_name = State()
    phone = State()
    city = State()
    contact_method = State()
    about_text = State()
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
        await message.answer("Сервис временно недоступен. Попробуйте позже.")
        return
    await state.set_state(ExecutorRegistration.legal_acceptance)
    await state.update_data(
        city_ids=[str(city.id) for city in cities],
        city_names=[city.name for city in cities],
        legal_document_ids=[str(document.id) for document in documents],
    )
    await message.answer(format_legal_documents(documents))


@router.message(ExecutorRegistration.legal_acceptance, F.text.casefold() == "согласен")
async def accept_legal(message: Message, state: FSMContext) -> None:
    await state.set_state(ExecutorRegistration.full_name)
    await message.answer("Введите ФИО.")


@router.message(ExecutorRegistration.legal_acceptance)
async def reject_legal(message: Message) -> None:
    await message.answer("Для регистрации нужно написать: Согласен")


@router.message(ExecutorRegistration.full_name)
async def enter_full_name(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip():
        await message.answer("Введите ФИО текстом.")
        return
    await state.update_data(full_name=message.text.strip())
    await state.set_state(ExecutorRegistration.phone)
    await message.answer("Введите телефон.")


@router.message(ExecutorRegistration.phone)
async def enter_phone(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip():
        await message.answer("Введите телефон текстом.")
        return
    data = await state.get_data()
    await state.update_data(phone=message.text.strip())
    await state.set_state(ExecutorRegistration.city)
    await message.answer(format_cities_from_state(data))


@router.message(ExecutorRegistration.city)
async def enter_city(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    city_ids = _string_list(data["city_ids"])
    city_id = parse_city_choice(message.text or "", city_ids)
    if city_id is None:
        await message.answer(format_cities_from_state(data))
        return
    city_index = city_ids.index(str(city_id))
    await state.update_data(
        city_id=str(city_id),
        city_name=_string_list(data["city_names"])[city_index],
    )
    await state.set_state(ExecutorRegistration.contact_method)
    await message.answer(format_contact_methods())


@router.message(ExecutorRegistration.contact_method)
async def enter_contact_method(message: Message, state: FSMContext) -> None:
    method = CONTACT_METHODS.get(message.text or "")
    if method is None:
        await message.answer(format_contact_methods())
        return
    value, label = method
    await state.update_data(contact_method=value, contact_method_label=label)
    await state.set_state(ExecutorRegistration.about_text)
    await message.answer("Коротко расскажите о себе.")


@router.message(ExecutorRegistration.about_text)
async def enter_about_text(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip():
        await message.answer("Введите описание текстом.")
        return
    await state.update_data(about_text=message.text.strip())
    data = await state.get_data()
    await state.set_state(ExecutorRegistration.summary)
    await message.answer(
        "\n".join(
            (
                "Проверьте данные:",
                f"ФИО: {data['full_name']}",
                f"Телефон: {data['phone']}",
                f"Город: {data['city_name']}",
                f"Контакт: {data['contact_method_label']}",
                f"О себе: {data['about_text']}",
                "",
                "Напишите: Подтвердить или Редактировать",
            ),
        ),
    )


@router.message(ExecutorRegistration.summary, F.text.casefold() == "редактировать")
async def edit_registration(message: Message, state: FSMContext) -> None:
    await state.set_state(ExecutorRegistration.full_name)
    await message.answer("Введите ФИО.")


@router.message(ExecutorRegistration.summary, F.text.casefold() == "подтвердить")
async def confirm_registration(
    message: Message,
    state: FSMContext,
    backend_client: BackendClient,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    try:
        await backend_client.register_performer(
            telegram_id=telegram_user_context.telegram_id,
            full_name=str(data["full_name"]),
            phone=str(data["phone"]),
            city_id=UUID(str(data["city_id"])),
            contact_method=str(data["contact_method"]),
            about_text=str(data["about_text"]),
            telegram_username=telegram_user_context.username,
            accepted_legal_document_ids=tuple(
                UUID(document_id)
                for document_id in _string_list(data["legal_document_ids"])
            ),
        )
    except BackendValidationError:
        await message.answer("Приглашение недействительно или данные отклонены.")
        await state.clear()
        return
    except BackendClientError:
        await message.answer("Сервис временно недоступен. Попробуйте позже.")
        return
    await state.clear()
    await message.answer("Регистрация отправлена. Ожидайте активации администратора.")


@router.message(ExecutorRegistration.summary)
async def unknown_summary_action(message: Message) -> None:
    await message.answer("Напишите: Подтвердить или Редактировать")


def format_cities_from_state(data: dict[str, object]) -> str:
    class _City:
        def __init__(self, name: str) -> None:
            self.name = name

    return format_cities(
        tuple(_City(name) for name in _string_list(data["city_names"])),
    )


def _string_list(value: object) -> list[str]:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise TypeError("Expected string list in FSM state")


__all__ = ["ExecutorRegistration", "router", "start_registration"]

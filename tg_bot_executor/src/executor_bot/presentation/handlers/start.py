from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from executor_bot.infrastructure.http import BackendClient, BackendClientError
from executor_bot.presentation.handlers.registration import start_registration
from executor_bot.presentation.middlewares import TelegramUserContext

router = Router(name="start")


@router.message(CommandStart())
async def start(
    message: Message,
    state: FSMContext,
    backend_client: BackendClient,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        registration_state = await backend_client.get_registration_state(
            telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await message.answer("Сервис временно недоступен. Попробуйте позже.")
        return
    if registration_state.state == "registered":
        await state.clear()
        await message.answer("Профиль исполнителя найден. Ожидайте сценарии заказов.")
        return
    if registration_state.state == "no_invitation":
        await state.clear()
        await message.answer("Регистрация доступна только по приглашению.")
        return
    await start_registration(message, state, backend_client)


__all__ = ["router", "start"]

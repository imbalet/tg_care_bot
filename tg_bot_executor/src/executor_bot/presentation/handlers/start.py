from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from executor_bot.infrastructure.http import BackendClient, BackendClientError
from executor_bot.presentation.handlers.registration import start_registration
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.ui import (
    executor_main_menu_text,
    main_menu_keyboard,
    no_invitation_text,
    retry_later_text,
)

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
        await message.answer(retry_later_text())
        return
    if registration_state.state == "registered":
        await state.clear()
        await message.answer(
            executor_main_menu_text(), reply_markup=main_menu_keyboard()
        )
        return
    if registration_state.state == "no_invitation":
        await state.clear()
        await message.answer(no_invitation_text())
        return
    await start_registration(message, state, backend_client)


__all__ = ["router", "start"]

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from customer_bot.infrastructure.http import BackendClient, BackendClientError
from customer_bot.presentation.handlers.registration import start_registration
from customer_bot.presentation.middlewares import TelegramUserContext
from customer_bot.presentation.ui import (
    customer_main_menu_text,
    main_menu_keyboard,
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
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await message.answer(retry_later_text())
        return
    if profile is not None:
        await state.clear()
        await message.answer(
            customer_main_menu_text(), reply_markup=main_menu_keyboard()
        )
        return
    await start_registration(message, state, backend_client)


__all__ = ["router", "start"]

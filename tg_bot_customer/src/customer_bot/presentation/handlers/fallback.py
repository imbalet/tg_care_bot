from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from customer_bot.infrastructure.http import BackendClient, BackendClientError
from customer_bot.presentation.middlewares import TelegramUserContext
from customer_bot.presentation.ui import (
    customer_main_menu_text,
    customer_profile_text,
    fallback_keyboard,
    fallback_text,
    help_text,
    main_menu_keyboard,
    unavailable_action_text,
)
from customer_bot.presentation.ui.keyboards import HELP, MAIN_MENU

router = Router(name="fallback")


@router.callback_query(F.data == MAIN_MENU)
async def main_menu_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    message = callback.message
    if isinstance(message, Message):
        await message.answer(
            customer_main_menu_text(), reply_markup=main_menu_keyboard()
        )


@router.callback_query(F.data == HELP)
async def help_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    message = callback.message
    if isinstance(message, Message):
        await message.answer(help_text(), reply_markup=fallback_keyboard())


@router.callback_query(F.data == "profile:open")
async def profile_callback(
    callback: CallbackQuery,
    backend_client: BackendClient,
    telegram_user_context: TelegramUserContext,
) -> None:
    await callback.answer()
    message = callback.message
    if not isinstance(message, Message):
        return
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await message.answer(
            unavailable_action_text(), reply_markup=fallback_keyboard()
        )
        return
    if profile is None:
        await message.answer(fallback_text(), reply_markup=fallback_keyboard())
        return
    await message.answer(
        customer_profile_text(profile), reply_markup=fallback_keyboard()
    )


@router.callback_query()
async def unknown_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    message = callback.message
    if isinstance(message, Message):
        await message.answer(
            unavailable_action_text(), reply_markup=fallback_keyboard()
        )


@router.message()
async def unknown_message(message: Message) -> None:
    await message.answer(fallback_text(), reply_markup=fallback_keyboard())


__all__ = [
    "help_callback",
    "main_menu_callback",
    "profile_callback",
    "router",
    "unknown_message",
]

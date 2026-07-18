from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from executor_bot.infrastructure.http import BackendClient, BackendClientError
from executor_bot.presentation.handlers.registration import start_registration
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.services import MenuManager
from executor_bot.presentation.ui import (
    executor_main_menu_text,
    fallback_keyboard,
    help_text,
    main_menu_keyboard,
    no_invitation_text,
    retry_later_text,
)

router = Router(name="start")


@router.message(CommandStart())
async def start(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendClient,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    await _open_start_or_menu(
        message=message,
        bot=bot,
        state=state,
        backend_client=backend_client,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        start_registration_if_invited=True,
    )


@router.message(Command("menu"))
async def menu(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendClient,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    await _open_start_or_menu(
        message=message,
        bot=bot,
        state=state,
        backend_client=backend_client,
        menu_manager=menu_manager,
        telegram_user_context=telegram_user_context,
        start_registration_if_invited=False,
    )


@router.message(Command("help"))
async def help_command(
    message: Message,
    bot: Bot,
    backend_client: BackendClient,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    include_main_menu = False
    try:
        include_main_menu = (
            await backend_client.get_registration_state(
                telegram_user_context.telegram_id
            )
        ).state == "registered"
    except BackendClientError:
        include_main_menu = False
    await menu_manager.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=help_text(),
        reply_markup=fallback_keyboard(include_main_menu=include_main_menu),
    )


async def _open_start_or_menu(
    *,
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendClient,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
    start_registration_if_invited: bool,
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
        await menu_manager.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=executor_main_menu_text(),
            reply_markup=main_menu_keyboard(),
        )
        return
    if registration_state.state == "no_invitation":
        await state.clear()
        await message.answer(no_invitation_text())
        return
    if start_registration_if_invited:
        await start_registration(message, state, backend_client)
        return
    await menu_manager.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=help_text(),
        reply_markup=fallback_keyboard(include_main_menu=False),
    )


__all__ = ["help_command", "menu", "router", "start"]

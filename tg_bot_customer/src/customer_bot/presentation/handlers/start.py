from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.registration import start_registration
from customer_bot.presentation.services import MenuManager, TelegramTopicSetupService
from customer_bot.presentation.ui import (
    customer_main_menu_text,
    fallback_keyboard,
    help_text,
    main_menu_keyboard,
    retry_later_text,
)

router = Router(name="start")


@router.message(CommandStart())
async def start(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    menu_manager: MenuManager,
    topic_setup_service: TelegramTopicSetupService,
    telegram_user_context: TelegramUserContext,
) -> None:
    await _open_start_or_menu(
        message=message,
        bot=bot,
        state=state,
        backend_client=backend_client,
        menu_manager=menu_manager,
        topic_setup_service=topic_setup_service,
        telegram_user_context=telegram_user_context,
        start_registration_if_missing=True,
    )


@router.message(Command("menu"))
async def menu(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    menu_manager: MenuManager,
    topic_setup_service: TelegramTopicSetupService,
    telegram_user_context: TelegramUserContext,
) -> None:
    await _open_start_or_menu(
        message=message,
        bot=bot,
        state=state,
        backend_client=backend_client,
        menu_manager=menu_manager,
        topic_setup_service=topic_setup_service,
        telegram_user_context=telegram_user_context,
        start_registration_if_missing=False,
    )


@router.message(Command("help"))
async def help_command(
    message: Message,
    bot: Bot,
    backend_client: BackendPort,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    include_main_menu = False
    try:
        include_main_menu = (
            await backend_client.get_customer_profile(telegram_user_context.telegram_id)
        ) is not None
    except BackendClientError:
        include_main_menu = False
    topic_key = await menu_manager.topic_key(
        telegram_id=telegram_user_context.telegram_id,
        message_thread_id=telegram_user_context.message_thread_id,
    )
    await menu_manager.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        topic_key=topic_key,
        text=help_text(),
        reply_markup=fallback_keyboard(include_main_menu=include_main_menu),
        message_thread_id=telegram_user_context.message_thread_id,
    )


async def _open_start_or_menu(
    *,
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    menu_manager: MenuManager,
    topic_setup_service: TelegramTopicSetupService,
    telegram_user_context: TelegramUserContext,
    start_registration_if_missing: bool,
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
        if telegram_user_context.chat_id is not None:
            await topic_setup_service.ensure(
                bot=bot,
                backend_client=backend_client,
                telegram_id=telegram_user_context.telegram_id,
                chat_id=telegram_user_context.chat_id,
            )
        topic_key = await menu_manager.topic_key(
            telegram_id=telegram_user_context.telegram_id,
            message_thread_id=telegram_user_context.message_thread_id,
        )
        await menu_manager.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            topic_key=topic_key,
            text=customer_main_menu_text(topic_key),
            reply_markup=main_menu_keyboard(topic_key),
            message_thread_id=telegram_user_context.message_thread_id,
        )
        return
    if start_registration_if_missing:
        await start_registration(message, state, backend_client)
        return
    await menu_manager.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        topic_key="general",
        text=help_text(),
        reply_markup=fallback_keyboard(include_main_menu=False),
        message_thread_id=telegram_user_context.message_thread_id,
    )

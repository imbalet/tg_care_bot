from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from customer_bot.infrastructure.http import BackendClient, BackendClientError
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.services import MenuManager
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
async def main_menu_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendClient,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer("Сообщение недоступно", show_alert=True)
        return
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await menu_manager.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            topic_key="general",
            text=unavailable_action_text(),
            reply_markup=fallback_keyboard(),
            message_thread_id=telegram_user_context.message_thread_id,
        )
        return
    if profile is None:
        await menu_manager.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            topic_key="general",
            text=help_text(),
            reply_markup=fallback_keyboard(include_main_menu=False),
            message_thread_id=telegram_user_context.message_thread_id,
        )
        return
    topic_key = await menu_manager.topic_key(
        telegram_id=telegram_user_context.telegram_id,
        message_thread_id=telegram_user_context.message_thread_id,
    )
    await menu_manager.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        topic_key=topic_key,
        text=customer_main_menu_text(topic_key),
        reply_markup=main_menu_keyboard(topic_key),
        message_thread_id=telegram_user_context.message_thread_id,
    )


@router.callback_query(F.data == HELP)
async def help_callback(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendClient,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    message = callback.message
    if isinstance(message, Message):
        current_state = await state.get_state()
        include_main_menu = current_state is None
        if include_main_menu:
            try:
                include_main_menu = (
                    await backend_client.get_customer_profile(
                        telegram_user_context.telegram_id,
                    )
                    is not None
                )
            except BackendClientError:
                include_main_menu = False
        topic_key = await menu_manager.topic_key(
            telegram_id=telegram_user_context.telegram_id,
            message_thread_id=telegram_user_context.message_thread_id,
        )
        await menu_manager.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            topic_key=topic_key,
            text=help_text(),
            reply_markup=fallback_keyboard(include_main_menu=include_main_menu),
            message_thread_id=telegram_user_context.message_thread_id,
        )


@router.callback_query(F.data == "profile:open")
async def profile_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendClient,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer("Сообщение недоступно", show_alert=True)
        return
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await menu_manager.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            topic_key="general",
            text=unavailable_action_text(),
            reply_markup=fallback_keyboard(),
            message_thread_id=telegram_user_context.message_thread_id,
        )
        return
    if profile is None:
        await menu_manager.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            topic_key="general",
            text=fallback_text(),
            reply_markup=fallback_keyboard(),
            message_thread_id=telegram_user_context.message_thread_id,
        )
        return
    topic_key = await menu_manager.topic_key(
        telegram_id=telegram_user_context.telegram_id,
        message_thread_id=telegram_user_context.message_thread_id,
    )
    await menu_manager.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        topic_key=topic_key,
        text=customer_profile_text(profile),
        reply_markup=fallback_keyboard(),
        message_thread_id=telegram_user_context.message_thread_id,
    )


@router.callback_query()
async def unknown_callback(
    callback: CallbackQuery,
    bot: Bot,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    topic_key = await menu_manager.topic_key(
        telegram_id=telegram_user_context.telegram_id,
        message_thread_id=telegram_user_context.message_thread_id,
    )
    await menu_manager.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        topic_key=topic_key,
        text=unavailable_action_text(),
        reply_markup=fallback_keyboard(),
        message_thread_id=telegram_user_context.message_thread_id,
    )


@router.message()
async def unknown_message(
    message: Message,
    bot: Bot,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    topic_key = await menu_manager.topic_key(
        telegram_id=telegram_user_context.telegram_id,
        message_thread_id=telegram_user_context.message_thread_id,
    )
    await menu_manager.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        topic_key=topic_key,
        text=fallback_text(),
        reply_markup=fallback_keyboard(),
        message_thread_id=telegram_user_context.message_thread_id,
    )

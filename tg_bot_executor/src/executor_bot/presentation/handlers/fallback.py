from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from executor_bot.application.errors import BackendClientError
from executor_bot.application.ports import BackendPort
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.services import TelegramResponder
from executor_bot.presentation.ui import (
    executor_main_menu_text,
    executor_profile_text,
    fallback_keyboard,
    fallback_text,
    help_text,
    main_menu_keyboard,
    unavailable_action_text,
)
from executor_bot.presentation.ui.keyboards import HELP, MAIN_MENU

router = Router(name="fallback")


@router.callback_query(F.data == MAIN_MENU)
async def main_menu_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer("Сообщение недоступно", show_alert=True)
        return
    try:
        registration_state = await backend_client.get_registration_state(
            telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=unavailable_action_text(),
            reply_markup=fallback_keyboard(),
        )
        return
    if registration_state.state != "registered":
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=help_text(),
            reply_markup=fallback_keyboard(include_main_menu=False),
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=executor_main_menu_text(),
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == HELP)
async def help_callback(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    message = callback.message
    if isinstance(message, Message):
        current_state = await state.get_state()
        include_main_menu = False
        if current_state is None:
            try:
                include_main_menu = (
                    await backend_client.get_registration_state(
                        telegram_user_context.telegram_id,
                    )
                ).state == "registered"
            except BackendClientError:
                include_main_menu = False
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=help_text(),
            reply_markup=fallback_keyboard(include_main_menu=include_main_menu),
        )


@router.callback_query(F.data == "profile:open")
async def profile_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer("Сообщение недоступно", show_alert=True)
        return
    try:
        state = await backend_client.get_registration_state(
            telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=unavailable_action_text(),
            reply_markup=fallback_keyboard(),
        )
        return
    if state.performer is None:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=fallback_text(),
            reply_markup=fallback_keyboard(),
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=executor_profile_text(state.performer),
        reply_markup=fallback_keyboard(),
    )


@router.callback_query()
async def unknown_callback(
    callback: CallbackQuery,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=unavailable_action_text(),
        reply_markup=fallback_keyboard(),
    )


@router.message()
async def unknown_message(
    message: Message,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=fallback_text(),
        reply_markup=fallback_keyboard(),
    )


__all__ = [
    "help_callback",
    "main_menu_callback",
    "profile_callback",
    "router",
    "unknown_message",
]

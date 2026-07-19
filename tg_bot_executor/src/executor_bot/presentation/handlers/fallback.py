from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from executor_bot.application.errors import BackendClientError
from executor_bot.application.ports import ActiveCategoryStore, BackendPort
from executor_bot.presentation.callbacks import (
    HelpCallback,
    MainMenuCallback,
    ProfileOpenCallback,
    SupportOpenCallback,
)
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.navigation import (
    active_category,
    show_category_menu,
    show_category_select,
)
from executor_bot.presentation.services import TelegramResponder
from executor_bot.presentation.ui import (
    executor_profile_text,
    fallback_keyboard,
    fallback_text,
    help_text,
    stale_action_keyboard,
    stale_action_text,
    support_keyboard,
    support_text,
    unavailable_action_text,
)

router = Router(name="fallback")


@router.callback_query(MainMenuCallback.filter())
async def main_menu_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    active_category_store: ActiveCategoryStore,
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
    category = await active_category(
        backend_client=backend_client,
        active_category_store=active_category_store,
        telegram_id=telegram_user_context.telegram_id,
    )
    if category is None:
        await show_category_select(
            bot=bot,
            event=callback,
            telegram_user_context=telegram_user_context,
            backend_client=backend_client,
            telegram_responder=telegram_responder,
        )
        return
    await show_category_menu(
        bot=bot,
        event=callback,
        telegram_user_context=telegram_user_context,
        telegram_responder=telegram_responder,
        category=category,
    )


@router.callback_query(HelpCallback.filter())
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
        return
    await callback.answer("Сообщение недоступно", show_alert=True)


@router.callback_query(SupportOpenCallback.filter())
async def support_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        contact = await backend_client.get_support_contact()
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=stale_action_text(),
            reply_markup=stale_action_keyboard(),
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=support_text(label=contact.label, telegram_url=contact.telegram_url),
        reply_markup=support_keyboard(
            label=contact.label,
            telegram_url=contact.telegram_url,
        ),
    )


@router.callback_query(ProfileOpenCallback.filter())
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
        text=stale_action_text(),
        reply_markup=stale_action_keyboard(),
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
    "support_callback",
    "unknown_message",
]

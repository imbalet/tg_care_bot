from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import ActiveCategoryStore, BackendPort
from customer_bot.presentation.callbacks import (
    HelpCallback,
    MainMenuCallback,
    OrdersListCallback,
    ProfileOpenCallback,
    ServicesPricesCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.navigation import (
    MAIN_MENU_KEY,
    active_category,
    show_category_menu,
    show_category_select,
)
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui import (
    customer_profile_text,
    fallback_keyboard,
    fallback_text,
    help_text,
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
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
        if profile is None:
            await telegram_responder.update(
                bot=bot,
                event=callback,
                telegram_id=telegram_user_context.telegram_id,
                topic_key=MAIN_MENU_KEY,
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
    except BackendClientError:
        await _show_unavailable(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
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
    include_main_menu = await state.get_state() is None
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
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        topic_key=MAIN_MENU_KEY,
        text=help_text(),
        reply_markup=fallback_keyboard(include_main_menu=include_main_menu),
    )


@router.callback_query(ProfileOpenCallback.filter())
async def profile_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await _show_unavailable(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
        )
        return
    if profile is None:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            topic_key=MAIN_MENU_KEY,
            text=fallback_text(),
            reply_markup=fallback_keyboard(),
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        topic_key=MAIN_MENU_KEY,
        text=customer_profile_text(profile),
        reply_markup=fallback_keyboard(),
    )


@router.callback_query(OrdersListCallback.filter())
@router.callback_query(ServicesPricesCallback.filter())
async def unavailable_section(
    callback: CallbackQuery,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        topic_key=MAIN_MENU_KEY,
        text=unavailable_action_text(),
        reply_markup=fallback_keyboard(),
    )


@router.callback_query()
async def unknown_callback(
    callback: CallbackQuery,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await _show_unavailable(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
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
        topic_key=MAIN_MENU_KEY,
        text=fallback_text(),
        reply_markup=fallback_keyboard(),
    )


async def _show_unavailable(
    *,
    bot: Bot,
    event: CallbackQuery,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        topic_key=MAIN_MENU_KEY,
        text=unavailable_action_text(),
        reply_markup=fallback_keyboard(),
    )

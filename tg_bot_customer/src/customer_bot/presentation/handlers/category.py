from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import ActiveCategoryStore, BackendPort
from customer_bot.presentation.callbacks import (
    CategoryChangeCallback,
    CategorySelectCallback,
    ScenarioCancelCallback,
    ScenarioContinueCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.navigation import (
    MAIN_MENU_KEY,
    category_by_code,
    list_categories,
    show_category_menu,
    show_category_select,
)
from customer_bot.presentation.services import MenuManager
from customer_bot.presentation.ui import (
    fallback_keyboard,
    help_text,
    unavailable_action_text,
    unfinished_action_keyboard,
    unfinished_action_text,
)

router = Router(name="category")


@router.callback_query(CategorySelectCallback.filter())
async def select_category(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    active_category_store: ActiveCategoryStore,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
    callback_data: CategorySelectCallback,
) -> None:
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
        if profile is None:
            await menu_manager.update(
                bot=bot,
                event=callback,
                telegram_id=telegram_user_context.telegram_id,
                topic_key=MAIN_MENU_KEY,
                text=help_text(),
                reply_markup=fallback_keyboard(include_main_menu=False),
            )
            return
        categories = await list_categories(backend_client)
    except BackendClientError:
        await _show_unavailable(
            bot=bot,
            event=callback,
            menu_manager=menu_manager,
            telegram_user_context=telegram_user_context,
        )
        return
    category = category_by_code(categories, callback_data.code)
    if category is None:
        await show_category_select(
            bot=bot,
            event=callback,
            telegram_user_context=telegram_user_context,
            backend_client=backend_client,
            menu_manager=menu_manager,
        )
        return
    await active_category_store.set(
        telegram_user_context.telegram_id,
        category.code,
    )
    await show_category_menu(
        bot=bot,
        event=callback,
        telegram_user_context=telegram_user_context,
        menu_manager=menu_manager,
        category=category,
    )


@router.callback_query(CategoryChangeCallback.filter())
async def change_category(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    if await state.get_state() is not None:
        await menu_manager.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            topic_key=MAIN_MENU_KEY,
            text=unfinished_action_text(),
            reply_markup=unfinished_action_keyboard(),
        )
        return
    try:
        await show_category_select(
            bot=bot,
            event=callback,
            telegram_user_context=telegram_user_context,
            backend_client=backend_client,
            menu_manager=menu_manager,
        )
    except BackendClientError:
        await _show_unavailable(
            bot=bot,
            event=callback,
            menu_manager=menu_manager,
            telegram_user_context=telegram_user_context,
        )


@router.callback_query(ScenarioContinueCallback.filter())
async def continue_scenario(
    callback: CallbackQuery,
    menu_manager: MenuManager,
) -> None:
    await menu_manager.acknowledge(callback, "Продолжайте текущий сценарий")


@router.callback_query(ScenarioCancelCallback.filter())
async def cancel_scenario(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.clear()
    try:
        await show_category_select(
            bot=bot,
            event=callback,
            telegram_user_context=telegram_user_context,
            backend_client=backend_client,
            menu_manager=menu_manager,
        )
    except BackendClientError:
        await _show_unavailable(
            bot=bot,
            event=callback,
            menu_manager=menu_manager,
            telegram_user_context=telegram_user_context,
        )


async def _show_unavailable(
    *,
    bot: Bot,
    event: CallbackQuery,
    menu_manager: MenuManager,
    telegram_user_context: TelegramUserContext,
) -> None:
    await menu_manager.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        topic_key=MAIN_MENU_KEY,
        text=unavailable_action_text(),
        reply_markup=fallback_keyboard(),
    )

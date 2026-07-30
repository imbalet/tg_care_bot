import logging

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from executor_bot.application.errors import BackendClientError
from executor_bot.application.ports import ActiveCategoryStore, BackendPort
from executor_bot.presentation.callbacks import (
    CategoryChangeCallback,
    CategorySelectCallback,
)
from executor_bot.presentation.contexts import TelegramUserContext
from executor_bot.presentation.navigation import (
    category_by_code,
    list_categories,
    show_category_menu,
    show_category_select,
)
from executor_bot.presentation.services import TelegramResponder
from executor_bot.presentation.ui import (
    fallback_keyboard,
    help_text,
    unavailable_action_text,
)

router = Router(name="category")
logger = logging.getLogger(__name__)


@router.callback_query(CategorySelectCallback.filter())
async def select_category(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    active_category_store: ActiveCategoryStore,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: CategorySelectCallback,
) -> None:
    try:
        state = await backend_client.get_registration_state(
            telegram_user_context.telegram_id,
        )
        if state.state != "registered":
            await telegram_responder.update(
                bot=bot,
                event=callback,
                telegram_id=telegram_user_context.telegram_id,
                text=help_text(),
                reply_markup=fallback_keyboard(include_main_menu=False),
            )
            return
        categories = await list_categories(
            backend_client,
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to select category",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "category_code": callback_data.code,
                "exception_type": type(exc).__name__,
            },
        )
        await _show_unavailable(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
        )
        return
    category = category_by_code(categories, callback_data.code)
    if category is None:
        logger.warning(
            "Unknown category selected",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "category_code": callback_data.code,
            },
        )
        await show_category_select(
            bot=bot,
            event=callback,
            telegram_user_context=telegram_user_context,
            backend_client=backend_client,
            telegram_responder=telegram_responder,
        )
        return
    await active_category_store.set(
        telegram_user_context.telegram_id,
        category.code,
    )
    logger.info(
        "Executor category selected",
        extra={
            "telegram_id": telegram_user_context.telegram_id,
            "category_code": category.code,
        },
    )
    await show_category_menu(
        bot=bot,
        event=callback,
        telegram_user_context=telegram_user_context,
        telegram_responder=telegram_responder,
        category=category,
    )


@router.callback_query(CategoryChangeCallback.filter())
async def change_category(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.clear()
    try:
        await show_category_select(
            bot=bot,
            event=callback,
            telegram_user_context=telegram_user_context,
            backend_client=backend_client,
            telegram_responder=telegram_responder,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to show category selector",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await _show_unavailable(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
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
        text=unavailable_action_text(),
        reply_markup=fallback_keyboard(),
    )

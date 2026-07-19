import logging

from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import ActiveCategoryStore, BackendPort
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.registration import start_registration
from customer_bot.presentation.navigation import (
    active_category,
    show_category_menu,
    show_category_select,
)
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui import (
    fallback_keyboard,
    help_text,
    retry_later_text,
)

router = Router(name="start")
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def start(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    active_category_store: ActiveCategoryStore,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.clear()
    await _open_start_or_menu(
        message=message,
        bot=bot,
        state=state,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        active_category_store=active_category_store,
        telegram_user_context=telegram_user_context,
        start_registration_if_missing=True,
    )


@router.message(Command("menu"))
async def menu(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    active_category_store: ActiveCategoryStore,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.clear()
    await _open_start_or_menu(
        message=message,
        bot=bot,
        state=state,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        active_category_store=active_category_store,
        telegram_user_context=telegram_user_context,
        start_registration_if_missing=False,
    )


@router.message(Command("cancel"))
async def cancel(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    active_category_store: ActiveCategoryStore,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.clear()
    await _open_start_or_menu(
        message=message,
        bot=bot,
        state=state,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        active_category_store=active_category_store,
        telegram_user_context=telegram_user_context,
        start_registration_if_missing=False,
    )


@router.message(Command("help"))
async def help_command(
    message: Message,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    include_main_menu = False
    try:
        include_main_menu = (
            await backend_client.get_customer_profile(telegram_user_context.telegram_id)
        ) is not None
    except BackendClientError:
        include_main_menu = False
    await telegram_responder.update(
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
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    active_category_store: ActiveCategoryStore,
    telegram_user_context: TelegramUserContext,
    start_registration_if_missing: bool,
) -> None:
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to load customer profile for start/menu",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
            create_new=True,
        )
        return
    if profile is not None:
        logger.info(
            "Opening customer menu",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        category = await active_category(
            backend_client=backend_client,
            active_category_store=active_category_store,
            telegram_id=telegram_user_context.telegram_id,
        )
        if category is None:
            await show_category_select(
                bot=bot,
                event=message,
                telegram_user_context=telegram_user_context,
                backend_client=backend_client,
                telegram_responder=telegram_responder,
            )
            return
        await show_category_menu(
            bot=bot,
            event=message,
            telegram_user_context=telegram_user_context,
            telegram_responder=telegram_responder,
            category=category,
        )
        return
    if start_registration_if_missing:
        logger.info(
            "Starting customer registration",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await start_registration(
            message,
            state,
            backend_client,
            bot,
            telegram_responder,
            telegram_user_context,
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=help_text(),
        reply_markup=fallback_keyboard(include_main_menu=False),
        create_new=True,
    )

import logging
from typing import NamedTuple

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
from customer_bot.presentation.ui.screens import HelpScreen, RetryLaterScreen


class IncludeMainMenu(NamedTuple):
    include_main_menu: bool
    legal_documents: tuple[object, ...] = ()


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
        force_create_new=True,
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
        force_create_new=True,
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
        force_create_new=True,
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

    try:
        documents = await backend_client.list_active_legal_documents()
    except BackendClientError:
        documents = ()
    screen = HelpScreen(
        IncludeMainMenu(include_main_menu, documents)
    ).build()
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
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
    force_create_new: bool = False,
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
        screen = RetryLaterScreen().build()
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=screen.text,
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
                force_create_new=force_create_new,
            )
            return
        await show_category_menu(
            bot=bot,
            event=message,
            telegram_user_context=telegram_user_context,
            telegram_responder=telegram_responder,
            category=category,
            force_create_new=force_create_new,
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
    try:
        documents = await backend_client.list_active_legal_documents()
    except BackendClientError:
        documents = ()
    screen = HelpScreen(IncludeMainMenu(False, documents)).build()
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )

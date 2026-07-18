import logging

from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from executor_bot.application.errors import BackendClientError
from executor_bot.application.ports import BackendPort
from executor_bot.presentation.handlers.registration import start_registration
from executor_bot.presentation.handlers.responses import send_screen, send_step
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.services import TelegramResponder
from executor_bot.presentation.ui import (
    executor_main_menu_text,
    fallback_keyboard,
    help_text,
    main_menu_keyboard,
    no_invitation_text,
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
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.clear()
    await _open_start_or_menu(
        message=message,
        bot=bot,
        state=state,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        start_registration_if_invited=True,
    )


@router.message(Command("menu"))
async def menu(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.clear()
    await _open_start_or_menu(
        message=message,
        bot=bot,
        state=state,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        start_registration_if_invited=False,
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
            await backend_client.get_registration_state(
                telegram_user_context.telegram_id
            )
        ).state == "registered"
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
    telegram_user_context: TelegramUserContext,
    start_registration_if_invited: bool,
) -> None:
    try:
        registration_state = await backend_client.get_registration_state(
            telegram_user_context.telegram_id,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to load performer registration state for start/menu",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    if registration_state.state == "registered":
        logger.info(
            "Opening executor menu",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=executor_main_menu_text(),
            reply_markup=main_menu_keyboard(),
        )
        return
    if registration_state.state == "no_invitation":
        await send_screen(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=no_invitation_text(),
        )
        return
    if start_registration_if_invited:
        logger.info(
            "Starting executor registration",
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
    await send_screen(
        bot=bot,
        event=message,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=help_text(),
        reply_markup=fallback_keyboard(include_main_menu=False),
    )


__all__ = ["help_command", "menu", "router", "start"]

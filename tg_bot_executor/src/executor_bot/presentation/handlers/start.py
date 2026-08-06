import logging

from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from executor_bot.application.errors import BackendClientError
from executor_bot.application.ports import ActiveCategoryStore, BackendPort
from executor_bot.presentation.handlers.registration import start_registration
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.navigation import (
    active_category,
    show_category_menu,
    show_category_select,
)
from executor_bot.presentation.services import TelegramResponder
from executor_bot.presentation.ui import (
    executor_setup_hint_text,
    fallback_keyboard,
    help_text,
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
        start_registration_if_invited=True,
        clear_reply_keyboard=True,
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
    try:
        documents = await backend_client.list_active_legal_documents()
    except BackendClientError:
        documents = ()
    try:
        contact = await backend_client.get_support_contact()
    except BackendClientError:
        contact = None
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=help_text(),
        reply_markup=fallback_keyboard(
            include_main_menu=True,
            include_help=False,
            include_support=False,
            support_label=contact.label if contact is not None else "Поддержка",
            support_url=contact.telegram_url if contact is not None else None,
            legal_documents=documents,
        ),
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
    start_registration_if_invited: bool,
    clear_reply_keyboard: bool = False,
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
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
            clear_reply_keyboard=clear_reply_keyboard,
        )
        return
    if registration_state.state == "registered":
        logger.info(
            "Opening executor menu",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        setup_hint = await _setup_hint(
            backend_client=backend_client,
            telegram_id=telegram_user_context.telegram_id,
            is_accepting_orders=bool(
                registration_state.performer
                and registration_state.performer.is_accepting_orders
            ),
            has_work_address=bool(
                registration_state.performer
                and registration_state.performer.current_address_id
            ),
        )
        if setup_hint is not None:
            await telegram_responder.send_notice(
                bot=bot,
                event=message,
                telegram_id=telegram_user_context.telegram_id,
                text=setup_hint,
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
                force_create_new=True,
                clear_reply_keyboard=clear_reply_keyboard,
            )
            return
        await show_category_menu(
            bot=bot,
            event=message,
            telegram_user_context=telegram_user_context,
            telegram_responder=telegram_responder,
            category=category,
            force_create_new=True,
            clear_reply_keyboard=clear_reply_keyboard,
        )
        return
    if registration_state.state == "no_invitation":
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=no_invitation_text(),
            clear_reply_keyboard=clear_reply_keyboard,
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
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=help_text(),
        reply_markup=fallback_keyboard(include_main_menu=True),
        clear_reply_keyboard=clear_reply_keyboard,
    )


async def _setup_hint(
    *,
    backend_client: BackendPort,
    telegram_id: int,
    is_accepting_orders: bool,
    has_work_address: bool,
) -> str | None:
    try:
        calendar = await backend_client.get_calendar(telegram_id=telegram_id)
        services = await backend_client.list_performer_services(
            telegram_id=telegram_id,
        )
    except BackendClientError:
        logger.info(
            "Skipped executor setup hint because setup state is unavailable",
            extra={"telegram_id": telegram_id},
        )
        return None
    missing: list[str] = []
    if calendar.schedule is None:
        missing.append("schedule")
    if not any(item.is_approved and item.is_enabled for item in services):
        missing.append("service")
    if not has_work_address:
        missing.append("address")
    if not is_accepting_orders:
        missing.append("accepting_orders")
    return executor_setup_hint_text(tuple(missing)) if missing else None


__all__ = ["help_command", "menu", "router", "start"]

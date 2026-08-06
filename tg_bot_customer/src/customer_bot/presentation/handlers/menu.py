import logging

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import ActiveCategoryStore, BackendPort
from customer_bot.presentation.callbacks import (
    CloseMessageCallback,
    HelpCallback,
    MainMenuCallback,
    ServicesPricesCallback,
    SupportOpenCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.navigation import (
    active_category,
    show_category_menu,
    show_category_select,
)
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.screens import (
    FallbackScreen,
    HelpScreen,
    ServicesPricesScreen,
    StaleActionScreen,
    SupportScreen,
)
from customer_bot.presentation.view_models import (
    HelpView,
)

router = Router(name="fallback")
logger = logging.getLogger(__name__)


@router.callback_query(CloseMessageCallback.filter())
async def close_message_callback(
    callback: CallbackQuery,
    telegram_responder: TelegramResponder,
) -> None:
    await telegram_responder.delete_clicked_message(callback)


@router.callback_query(MainMenuCallback.filter())
async def main_menu_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    active_category_store: ActiveCategoryStore,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await telegram_responder.clear_reply_keyboard(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
    )
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
        if profile is None:
            try:
                contact = await backend_client.get_support_contact()
            except BackendClientError:
                contact = None
            screen = HelpScreen(
                HelpView(
                    include_main_menu=True,
                    support_label=(
                        contact.label if contact is not None else "Поддержка"
                    ),
                    support_telegram_url=(
                        contact.telegram_url if contact is not None else None
                    ),
                )
            ).build()
            await telegram_responder.update(
                bot=bot,
                event=callback,
                telegram_id=telegram_user_context.telegram_id,
                text=screen.text,
                reply_markup=screen.reply_markup,
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
    except BackendClientError as exc:
        logger.warning(
            "Failed to open main menu callback",
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
        except BackendClientError as exc:
            logger.warning(
                "Failed to check profile for help callback",
                extra={
                    "telegram_id": telegram_user_context.telegram_id,
                    "exception_type": type(exc).__name__,
                },
            )
            include_main_menu = False
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
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := HelpScreen(
                HelpView(
                    include_main_menu=include_main_menu,
                    legal_documents=documents,
                    support_label=(
                        contact.label if contact is not None else "Поддержка"
                    ),
                    support_telegram_url=(
                        contact.telegram_url if contact is not None else None
                    ),
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
    )


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
    except BackendClientError as exc:
        logger.warning(
            "Failed to load support contact",
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
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := SupportScreen(contact).build()).text,
        reply_markup=screen.reply_markup,
    )


@router.callback_query(ServicesPricesCallback.filter())
async def services_prices_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    active_category_store: ActiveCategoryStore,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
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
    except BackendClientError as exc:
        logger.warning(
            "Failed to open services prices",
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
        return

    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := ServicesPricesScreen(category).build()).text,
        reply_markup=screen.reply_markup,
    )


@router.callback_query()
async def unknown_callback(
    callback: CallbackQuery,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    logger.warning(
        "Unknown callback received",
        extra={"telegram_id": telegram_user_context.telegram_id},
    )
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
        text=(screen := FallbackScreen().build()).text,
        reply_markup=screen.reply_markup,
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
        text=(screen := StaleActionScreen().build()).text,
        reply_markup=screen.reply_markup,
    )

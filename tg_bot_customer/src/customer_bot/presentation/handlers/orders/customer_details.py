import logging
from uuid import UUID

from aiogram import Bot, Router
from aiogram.types import CallbackQuery

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    OrderLocationOpenCallback,
    OrderReportOpenCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.screens import (
    OrderLocationScreen,
    OrderReportScreen,
    RetryLaterScreen,
)

router = Router(name="customer_order_details")
logger = logging.getLogger(__name__)


async def _customer_id(backend_client: BackendPort, telegram_id: int) -> UUID:
    profile = await backend_client.get_customer_profile(telegram_id)
    if profile is None:
        raise BackendClientError("Customer profile is missing")
    return profile.id


async def _show_retry(
    *,
    bot: Bot,
    callback: CallbackQuery,
    telegram_responder: TelegramResponder,
    telegram_id: int,
) -> None:
    screen = RetryLaterScreen().build()
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.callback_query(OrderLocationOpenCallback.filter())
async def open_order_location(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderLocationOpenCallback,
) -> None:
    try:
        customer_id = await _customer_id(
            backend_client, telegram_user_context.telegram_id
        )
        location = await backend_client.get_customer_order_location(
            customer_id=customer_id,
            order_id=callback_data.order_id,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to load customer order location",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "order_id": str(callback_data.order_id),
                "exception_type": type(exc).__name__,
            },
        )
        await _show_retry(
            bot=bot,
            callback=callback,
            telegram_responder=telegram_responder,
            telegram_id=telegram_user_context.telegram_id,
        )
        return

    screen = OrderLocationScreen(location).build()
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.callback_query(OrderReportOpenCallback.filter())
async def open_order_report(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderReportOpenCallback,
) -> None:
    try:
        customer_id = await _customer_id(
            backend_client, telegram_user_context.telegram_id
        )
        report = await backend_client.get_customer_order_report(
            customer_id=customer_id,
            order_id=callback_data.order_id,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to load customer order report",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "order_id": str(callback_data.order_id),
                "exception_type": type(exc).__name__,
            },
        )
        await _show_retry(
            bot=bot,
            callback=callback,
            telegram_responder=telegram_responder,
            telegram_id=telegram_user_context.telegram_id,
        )
        return

    screen = OrderReportScreen(report).build()
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


__all__ = ["router"]

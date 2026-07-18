import logging
from uuid import UUID

from aiogram import Bot, Router
from aiogram.types import CallbackQuery

from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    OrderResponseRejectCallback,
    OrderResponseSelectCallback,
    OrderResponsesOpenCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.responses import send_step
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui import (
    order_matches_keyboard,
    order_matches_text,
    order_response_rejected_text,
    order_response_selected_text,
    order_response_unavailable_text,
    retry_later_text,
)

router = Router(name="orders_matches")
logger = logging.getLogger(__name__)


@router.callback_query(OrderResponsesOpenCallback.filter())
async def open_order_matches(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderResponsesOpenCallback,
) -> None:
    try:
        customer_id = await _customer_id(
            backend_client=backend_client,
            telegram_id=telegram_user_context.telegram_id,
        )
        matches = await backend_client.list_order_matches(
            order_id=callback_data.order_id,
            customer_id=customer_id,
        )
    except BackendValidationError:
        logger.warning(
            "Backend rejected order matches request",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=order_response_unavailable_text(),
        )
        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to load order matches",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return

    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_matches_text(matches),
        reply_markup=order_matches_keyboard(matches),
    )


@router.callback_query(OrderResponseSelectCallback.filter())
async def select_order_match(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderResponseSelectCallback,
) -> None:
    try:
        customer_id = await _customer_id(
            backend_client=backend_client,
            telegram_id=telegram_user_context.telegram_id,
        )
        action = await backend_client.select_pool_response(
            match_id=callback_data.match_id,
            customer_id=customer_id,
        )
    except BackendValidationError:
        logger.warning(
            "Backend rejected order match selection",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=order_response_unavailable_text(),
        )
        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to select order match",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return

    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_response_selected_text(action),
    )


@router.callback_query(OrderResponseRejectCallback.filter())
async def reject_order_match(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderResponseRejectCallback,
) -> None:
    try:
        customer_id = await _customer_id(
            backend_client=backend_client,
            telegram_id=telegram_user_context.telegram_id,
        )
        await backend_client.reject_pool_response(
            match_id=callback_data.match_id,
            customer_id=customer_id,
        )
    except BackendValidationError:
        logger.warning(
            "Backend rejected order match rejection",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=order_response_unavailable_text(),
        )
        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to reject order match",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return

    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_response_rejected_text(),
    )


async def _customer_id(*, backend_client: BackendPort, telegram_id: int) -> UUID:
    profile = await backend_client.get_customer_profile(telegram_id)
    if profile is None:
        raise BackendClientError("Customer profile is missing")
    return profile.id

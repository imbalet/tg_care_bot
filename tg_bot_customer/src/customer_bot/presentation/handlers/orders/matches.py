import logging
from uuid import UUID

from aiogram import Bot, Router
from aiogram.types import CallbackQuery

from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    OrderResponsePerformerProfileCallback,
    OrderResponseRejectCallback,
    OrderResponseSelectCallback,
    OrderResponsesOpenCallback,
    PaymentRefreshCallback,
    PaymentRetryCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.services import TelegramResponder, show_performer_profile
from customer_bot.presentation.ui.screens import (
    OrderMatchesScreen,
    OrderResponseRejectedScreen,
    OrderResponseSelectedScreen,
    OrderResponseUnavailableScreen,
    PaymentStatusScreen,
    RetryLaterScreen,
)
from customer_bot.presentation.view_models import (
    PaymentStatusView,
    SelectedOrderResponseView,
)

router = Router(name="orders_matches")
logger = logging.getLogger(__name__)


@router.callback_query(OrderResponsePerformerProfileCallback.filter())
async def response_performer_profile(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderResponsePerformerProfileCallback,
) -> None:
    try:
        profile = await backend_client.get_public_performer_profile(
            telegram_id=telegram_user_context.telegram_id,
            performer_id=callback_data.performer_id,
        )
    except BackendClientError:
        await telegram_responder.acknowledge(
            callback, "Профиль исполнителя сейчас недоступен", show_alert=True
        )
        return
    await telegram_responder.acknowledge(callback)
    await show_performer_profile(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        profile=profile,
        telegram_responder=telegram_responder,
    )


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
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := OrderResponseUnavailableScreen().build()).text,
            reply_markup=screen.reply_markup,
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
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return

    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := OrderMatchesScreen(matches).build()).text,
        reply_markup=screen.reply_markup,
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
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := OrderResponseUnavailableScreen().build()).text,
            reply_markup=screen.reply_markup,
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
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return

    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := OrderResponseSelectedScreen(
                SelectedOrderResponseView(
                    order_status=action.order_status,
                    id=action.order_id,
                    payment_confirmation_url=action.payment_confirmation_url,
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
    )


@router.callback_query(PaymentRefreshCallback.filter())
async def refresh_payment_status(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: PaymentRefreshCallback,
) -> None:
    try:
        customer_id = await _customer_id(
            backend_client=backend_client,
            telegram_id=telegram_user_context.telegram_id,
        )
        status = await backend_client.get_payment_status(
            order_id=callback_data.order_id,
            customer_id=customer_id,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to refresh payment status",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return

    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := PaymentStatusScreen(
                PaymentStatusView(
                    id=status.order_id,
                    order_status=status.order_status,
                    payment_status=status.payment_status,
                    confirmation_url=status.confirmation_url,
                    expires_at=status.expires_at,
                    failure_code=status.failure_code,
                    attempts_used=status.attempts_used,
                    max_attempts=status.max_attempts,
                    retry_available=status.retry_available,
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
    )


@router.callback_query(PaymentRetryCallback.filter())
async def retry_payment(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: PaymentRetryCallback,
) -> None:
    try:
        customer_id = await _customer_id(
            backend_client=backend_client,
            telegram_id=telegram_user_context.telegram_id,
        )
        status = await backend_client.retry_payment(
            order_id=callback_data.order_id,
            customer_id=customer_id,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to retry payment",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return

    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := PaymentStatusScreen(
                PaymentStatusView(
                    id=status.order_id,
                    order_status=status.order_status,
                    payment_status=status.payment_status,
                    confirmation_url=status.confirmation_url,
                    expires_at=status.expires_at,
                    failure_code=status.failure_code,
                    attempts_used=status.attempts_used,
                    max_attempts=status.max_attempts,
                    retry_available=status.retry_available,
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
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
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := OrderResponseUnavailableScreen().build()).text,
            reply_markup=screen.reply_markup,
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
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return

    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := OrderResponseRejectedScreen().build()).text,
        reply_markup=screen.reply_markup,
    )


async def _customer_id(*, backend_client: BackendPort, telegram_id: int) -> UUID:
    profile = await backend_client.get_customer_profile(telegram_id)
    if profile is None:
        raise BackendClientError("Customer profile is missing")
    return profile.id

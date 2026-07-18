from uuid import UUID

from aiogram import Bot, Router
from aiogram.types import CallbackQuery

from executor_bot.application.errors import BackendClientError
from executor_bot.application.ports import BackendPort, ViewedAvailableOrdersStore
from executor_bot.presentation.callbacks import (
    AvailableOrdersOpenCallback,
    DirectAcceptCallback,
    DirectRejectCallback,
    ExecutorOrdersOpenCallback,
    PoolRespondCallback,
)
from executor_bot.presentation.contexts import TelegramUserContext
from executor_bot.presentation.services import TelegramResponder
from executor_bot.presentation.ui import (
    available_orders_keyboard,
    available_orders_text,
    direct_accept_created_text,
    direct_rejected_text,
    executor_orders_placeholder_text,
    orders_filter_keyboard,
    pool_response_created_text,
)

router = Router(name="orders")


@router.callback_query(AvailableOrdersOpenCallback.filter())
async def available_orders_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    viewed_available_orders_store: ViewedAvailableOrdersStore,
    callback_data: AvailableOrdersOpenCallback,
) -> None:
    state = await backend_client.get_registration_state(
        telegram_user_context.telegram_id,
    )
    if state.performer is None:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text="Профиль исполнителя не найден.",
            reply_markup=orders_filter_keyboard(is_available_orders=True),
        )
        return
    orders = await backend_client.list_available_orders(
        performer_id=state.performer.id,
    )
    viewed = await viewed_available_orders_store.list_viewed(
        telegram_user_context.telegram_id,
    )
    visible_orders = tuple(order for order in orders if str(order.id) not in viewed)
    for order in visible_orders:
        await viewed_available_orders_store.mark_viewed(
            telegram_user_context.telegram_id,
            str(order.id),
        )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=available_orders_text(visible_orders, callback_data.scope),
        reply_markup=available_orders_keyboard(visible_orders),
    )


@router.callback_query(ExecutorOrdersOpenCallback.filter())
async def executor_orders_callback(
    callback: CallbackQuery,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorOrdersOpenCallback,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=executor_orders_placeholder_text(callback_data.scope),
        reply_markup=orders_filter_keyboard(is_available_orders=False),
    )


@router.callback_query(PoolRespondCallback.filter())
async def pool_response_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: PoolRespondCallback,
) -> None:
    try:
        state = await backend_client.get_registration_state(
            telegram_user_context.telegram_id,
        )
        if state.performer is None:
            raise ValueError("Performer is not registered")
        await backend_client.create_pool_response(
            order_id=UUID(callback_data.order_id),
            performer_id=state.performer.id,
        )
        text = pool_response_created_text()
    except BackendClientError, ValueError:
        text = "Отклик уже недоступен. Откройте список заказов заново."
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=orders_filter_keyboard(is_available_orders=True),
    )


@router.callback_query(DirectAcceptCallback.filter())
async def direct_accept_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: DirectAcceptCallback,
) -> None:
    try:
        state = await backend_client.get_registration_state(
            telegram_user_context.telegram_id,
        )
        if state.performer is None:
            raise ValueError("Performer is not registered")
        await backend_client.accept_direct_match(
            match_id=UUID(callback_data.match_id),
            performer_id=state.performer.id,
        )
        text = direct_accept_created_text()
    except BackendClientError, ValueError:
        text = "Direct-приглашение уже недоступно."
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=orders_filter_keyboard(is_available_orders=False),
    )


@router.callback_query(DirectRejectCallback.filter())
async def direct_reject_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: DirectRejectCallback,
) -> None:
    try:
        state = await backend_client.get_registration_state(
            telegram_user_context.telegram_id,
        )
        if state.performer is None:
            raise ValueError("Performer is not registered")
        await backend_client.reject_direct_match(
            match_id=UUID(callback_data.match_id),
            performer_id=state.performer.id,
        )
        text = direct_rejected_text()
    except BackendClientError, ValueError:
        text = "Direct-приглашение уже недоступно."
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=orders_filter_keyboard(is_available_orders=False),
    )


__all__ = ["router"]

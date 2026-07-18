from aiogram import Bot, Router
from aiogram.types import CallbackQuery

from executor_bot.presentation.callbacks import (
    AvailableOrdersOpenCallback,
    ExecutorOrdersOpenCallback,
)
from executor_bot.presentation.contexts import TelegramUserContext
from executor_bot.presentation.services import TelegramResponder
from executor_bot.presentation.ui import (
    available_orders_placeholder_text,
    executor_orders_placeholder_text,
    orders_filter_keyboard,
)

router = Router(name="orders")


@router.callback_query(AvailableOrdersOpenCallback.filter())
async def available_orders_callback(
    callback: CallbackQuery,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: AvailableOrdersOpenCallback,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=available_orders_placeholder_text(callback_data.scope),
        reply_markup=orders_filter_keyboard(is_available_orders=True),
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


__all__ = ["router"]

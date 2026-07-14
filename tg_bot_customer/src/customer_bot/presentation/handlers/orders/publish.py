from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    OrderPublishDirectCallback,
    OrderPublishPoolCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.orders.state import (
    OrderCreation,
)
from customer_bot.presentation.handlers.orders.state import (
    draft as _draft,
)
from customer_bot.presentation.handlers.orders.state import (
    item_by_index as _item_by_index,
)
from customer_bot.presentation.handlers.responses import send_step
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui import (
    order_published_text,
    retry_later_text,
)

router = Router(name="orders_publish")


@router.callback_query(OrderCreation.publish, OrderPublishPoolCallback.filter())
async def publish_pool(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    draft = _draft(data)
    try:
        order = await backend_client.publish_order_pool(
            order_id=UUID(str(draft["order_id"])),
        )
    except BackendClientError:
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await state.clear()
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_published_text(order),
    )


@router.callback_query(
    OrderCreation.publish,
    OrderPublishDirectCallback.filter(),
)
async def publish_direct(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderPublishDirectCallback,
) -> None:
    performer = await _item_by_index(state, "order_performers", callback_data.index)
    if performer is None:
        return
    data = await state.get_data()
    draft = _draft(data)
    try:
        order = await backend_client.publish_order_direct(
            order_id=UUID(str(draft["order_id"])),
            performer_id=UUID(str(performer["performer_id"])),
        )
    except BackendClientError:
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await state.clear()
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_published_text(order),
    )

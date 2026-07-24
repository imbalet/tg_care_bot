import logging

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import ActiveCategoryStore, BackendPort
from customer_bot.presentation.callbacks import (
    OrderCreateCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.orders.creation_views import service_view
from customer_bot.presentation.handlers.orders.state import (
    OrderCreation,
    service_states,
)
from customer_bot.presentation.navigation import active_category
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.screens import (
    OrderNoServicesScreen,
    OrderServicesStepScreen,
    RetryLaterScreen,
    StaleActionScreen,
)
from customer_bot.presentation.view_models import (
    ServicesView,
)

router = Router(name="orders_create")
logger = logging.getLogger(__name__)


@router.callback_query(OrderCreateCallback.filter())
async def start_order_creation(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
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
    except BackendClientError as exc:
        logger.warning(
            "Failed to start order creation",
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
    if category is None:
        logger.warning(
            "Order creation requested without active category",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := StaleActionScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return
    services = service_states((category,))
    if not services:
        logger.warning(
            "Order creation category has no services",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "category_code": category.code,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := OrderNoServicesScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return
    await state.set_state(OrderCreation.service)
    await state.update_data(
        order_services=services,
        draft={
            "category_code": category.code,
            "category_name": category.name,
            "care_object_type": category.care_object_type,
        },
    )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := OrderServicesStepScreen(
                ServicesView(services=tuple(service_view(item) for item in services))
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
    )

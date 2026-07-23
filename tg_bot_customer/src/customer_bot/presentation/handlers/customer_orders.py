import logging
from uuid import UUID

from aiogram import Bot, Router
from aiogram.types import CallbackQuery

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import ActiveCategoryStore, BackendPort
from customer_bot.presentation.callbacks import (
    NotificationOrderOpenCallback,
    OrderCancelConfirmCallback,
    OrderCancelPreviewCallback,
    OrderCardOpenCallback,
    OrdersListCallback,
    OrdersPageCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.navigation import active_category
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.screens import (
    MyOrderCardScreen,
    MyOrdersPageScreen,
    OrderCancellationPreviewScreen,
    RetryLaterScreen,
    StaleActionScreen,
)
from customer_bot.presentation.view_models import (
    MyOrderCardView,
    MyOrdersPageView,
    OrderListItemView,
)

router = Router(name="customer_orders")
logger = logging.getLogger(__name__)


@router.callback_query(OrderCancelPreviewCallback.filter())
async def cancel_order_preview_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderCancelPreviewCallback,
) -> None:
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
        if profile is None:
            raise BackendClientError("Customer profile is missing")
        preview = await backend_client.get_customer_cancellation_preview(
            order_id=callback_data.order_id,
            customer_id=profile.id,
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := OrderCancellationPreviewScreen(preview).build()).text,
            reply_markup=screen.reply_markup,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to load cancellation preview",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "order_id": str(callback_data.order_id),
                "exception_type": type(exc).__name__,
            },
        )
        await _show_unavailable(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
        )


@router.callback_query(OrderCancelConfirmCallback.filter())
async def cancel_order_confirm_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderCancelConfirmCallback,
) -> None:
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
        if profile is None:
            raise BackendClientError("Customer profile is missing")
        await backend_client.cancel_customer_order(
            order_id=callback_data.order_id,
            customer_id=profile.id,
        )
        await _show_order_card(
            callback=callback,
            bot=bot,
            backend_client=backend_client,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            order_id=callback_data.order_id,
            group="archive",
            page=1,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to cancel customer order",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "order_id": str(callback_data.order_id),
                "exception_type": type(exc).__name__,
            },
        )
        await _show_unavailable(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
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
        text=(screen := RetryLaterScreen().build()).text,
        reply_markup=screen.reply_markup,
    )


@router.callback_query(OrdersListCallback.filter())
async def orders_list_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    active_category_store: ActiveCategoryStore,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    category = await active_category(
        backend_client=backend_client,
        active_category_store=active_category_store,
        telegram_id=telegram_user_context.telegram_id,
    )
    await _show_orders_page(
        bot=bot,
        event=callback,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        group="active",
        page=1,
        category_code=category.code if category is not None else None,
        active_category_code=category.code if category is not None else None,
    )


@router.callback_query(OrdersPageCallback.filter())
async def orders_page_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    active_category_store: ActiveCategoryStore,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrdersPageCallback,
) -> None:
    category = await active_category(
        backend_client=backend_client,
        active_category_store=active_category_store,
        telegram_id=telegram_user_context.telegram_id,
    )
    await _show_orders_page(
        bot=bot,
        event=callback,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        group=callback_data.group,
        page=callback_data.page,
        category_code=callback_data.category_code,
        active_category_code=category.code if category is not None else None,
    )


@router.callback_query(OrderCardOpenCallback.filter())
async def order_card_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderCardOpenCallback,
) -> None:
    await _show_order_card(
        callback=callback,
        bot=bot,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        order_id=callback_data.order_id,
        group=callback_data.group,
        page=callback_data.page,
    )


@router.callback_query(NotificationOrderOpenCallback.filter())
async def notification_order_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: NotificationOrderOpenCallback,
) -> None:
    await _show_order_card(
        callback=callback,
        bot=bot,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        order_id=callback_data.order_id,
        group="active",
        page=1,
    )


async def _show_order_card(
    *,
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    order_id: UUID,
    group: str,
    page: int,
) -> None:
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
        if profile is None:
            raise BackendClientError("Customer profile is missing")
        order = await backend_client.get_customer_order_card(
            customer_id=profile.id,
            order_id=order_id,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to open customer order card",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "order_id": str(order_id),
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
        text=(
            screen := MyOrderCardScreen(
                MyOrderCardView(
                    id=order.id,
                    service_name=order.service_name,
                    matching_mode=order.matching_mode,
                    status=order.status,
                    start_at=order.start_at,
                    end_at=order.end_at,
                    objects_count=order.objects_count,
                    total_amount=order.total_amount,
                    payment_deadline_at=order.payment_deadline_at,
                    matching_deadline_at=order.matching_deadline_at,
                    payment_status=order.payment_status,
                    payment_confirmation_url=order.payment_confirmation_url,
                    payment_expires_at=order.payment_expires_at,
                    group=group,
                    page=page,
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
    )


async def _show_orders_page(
    *,
    bot: Bot,
    event: CallbackQuery,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_id: int,
    group: str,
    page: int,
    category_code: str | None,
    active_category_code: str | None,
) -> None:
    try:
        profile = await backend_client.get_customer_profile(telegram_id)
        if profile is None:
            raise BackendClientError("Customer profile is missing")
        orders = await backend_client.list_customer_orders(
            customer_id=profile.id,
            group=group,
            page=page,
            category_code=category_code,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to load customer orders page",
            extra={
                "telegram_id": telegram_id,
                "group": group,
                "page": page,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_id,
            text=(screen := StaleActionScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_id,
        text=(
            screen := MyOrdersPageScreen(
                MyOrdersPageView(
                    items=tuple(
                        OrderListItemView(
                            id=item.id,
                            category_code=item.category_code,
                            service_name=item.service_name,
                            matching_mode=item.matching_mode,
                            status=item.status,
                            start_at=item.start_at,
                            end_at=item.end_at,
                            objects_count=item.objects_count,
                            total_amount=item.total_amount,
                            payment_deadline_at=item.payment_deadline_at,
                            matching_deadline_at=item.matching_deadline_at,
                        )
                        for item in orders.items
                    ),
                    page=orders.page,
                    total_pages=orders.total_pages,
                    total_items=orders.total_items,
                    group=group,
                    category_code=category_code,
                    active_category_code=active_category_code,
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
    )


__all__ = ["router"]

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
    OrderCardOpenCallback,
    OrdersListCallback,
    OrdersPageCallback,
    ProfileOpenCallback,
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
    MyOrderCardScreen,
    MyOrdersPageScreen,
    ProfileScreen,
    ServicesPricesScreen,
    StaleActionScreen,
    SupportScreen,
)
from customer_bot.presentation.view_models import (
    HelpView,
    MyOrderCardView,
    MyOrdersPageView,
    OrderListItemView,
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
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
        if profile is None:
            await telegram_responder.update(
                bot=bot,
                event=callback,
                telegram_id=telegram_user_context.telegram_id,
                text=(
                    screen := HelpScreen(HelpView(include_main_menu=False)).build()
                ).text,
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
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := HelpScreen(HelpView(include_main_menu=include_main_menu)).build()
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


@router.callback_query(ProfileOpenCallback.filter())
async def profile_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to open customer profile",
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
    if profile is None:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := FallbackScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := ProfileScreen(profile).build()).text,
        reply_markup=screen.reply_markup,
    )


@router.callback_query(OrdersListCallback.filter())
async def orders_list_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await _show_orders_page(
        bot=bot,
        event=callback,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        group="active",
        page=1,
    )


@router.callback_query(OrdersPageCallback.filter())
async def orders_page_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrdersPageCallback,
) -> None:
    await _show_orders_page(
        bot=bot,
        event=callback,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        group=callback_data.group,
        page=callback_data.page,
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
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
        if profile is None:
            raise BackendClientError("Customer profile is missing")
        order = await backend_client.get_customer_order_card(
            customer_id=profile.id,
            order_id=callback_data.order_id,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to open customer order card",
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
                    group=callback_data.group,
                    page=callback_data.page,
                )
            ).build()
        ).text,
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


async def _show_orders_page(
    *,
    bot: Bot,
    event: CallbackQuery,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_id: int,
    group: str,
    page: int,
) -> None:
    try:
        profile = await backend_client.get_customer_profile(telegram_id)
        if profile is None:
            raise BackendClientError("Customer profile is missing")
        orders = await backend_client.list_customer_orders(
            customer_id=profile.id,
            group=group,
            page=page,
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
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
    )

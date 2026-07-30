import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    OrderDirectBackCallback,
    OrderDirectNextCallback,
    OrderDirectOpenCallback,
    OrderDirectPerformerProfileCallback,
    OrderDirectPreviousCallback,
    OrderPublishDirectCallback,
    OrderPublishPoolCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.orders.state import (
    OrderCreation,
    OrderDraftSnapshot,
    OrderSummarySnapshot,
    draft,
    item_by_id,
    performer_view,
)
from customer_bot.presentation.services import TelegramResponder, show_performer_profile
from customer_bot.presentation.ui.screens import (
    OrderDirectSelectionScreen,
    OrderDirectUnavailableScreen,
    OrderDraftSummaryScreen,
    OrderPublishedScreen,
    RetryLaterScreen,
)
from customer_bot.presentation.view_models import OrderSummaryView, PerformerView

router = Router(name="orders_publish")
logger = logging.getLogger(__name__)


async def _show_direct_performer(
    event: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    index: int,
) -> None:
    data = await state.get_data()
    raw_performers = data.get("order_performers")
    if not isinstance(raw_performers, list):
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=False,
        )
        return
    performers = [item for item in raw_performers if isinstance(item, dict)]
    if not performers:
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := OrderDirectUnavailableScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=False,
        )
        return
    index = max(0, min(index, len(performers) - 1))
    view = performer_view(performers[index])
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := OrderDirectSelectionScreen(
                _DirectSelectionView(
                    performer=view,
                    index=index,
                    total=len(performers),
                ),
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=False,
    )


@router.callback_query(OrderCreation.publish, OrderDirectOpenCallback.filter())
async def open_direct_selection(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.update_data(order_performer_index=0)
    await _show_direct_performer(
        callback, bot, state, telegram_responder, telegram_user_context, 0
    )


@router.callback_query(OrderCreation.publish, OrderDirectNextCallback.filter())
async def next_direct_performer(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    index = data.get("order_performer_index", 0)
    current = int(index) if isinstance(index, int) else 0
    await state.update_data(order_performer_index=current + 1)
    await _show_direct_performer(
        callback, bot, state, telegram_responder, telegram_user_context, current + 1
    )


@router.callback_query(
    OrderCreation.publish, OrderDirectPerformerProfileCallback.filter()
)
async def direct_performer_profile(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderDirectPerformerProfileCallback,
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
        back_direct=True,
    )


@router.callback_query(OrderCreation.publish, OrderDirectPreviousCallback.filter())
async def previous_direct_performer(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    index = data.get("order_performer_index", 0)
    current = int(index) if isinstance(index, int) else 0
    await state.update_data(order_performer_index=max(0, current - 1))
    await _show_direct_performer(
        callback, bot, state, telegram_responder, telegram_user_context, current - 1
    )


@router.callback_query(OrderCreation.publish, OrderDirectBackCallback.filter())
async def back_from_direct_selection(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    summary = data.get("order_summary")
    if not isinstance(summary, dict):
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=False,
        )
        return
    try:
        summary_view = OrderSummarySnapshot.from_data(summary)
    except KeyError, TypeError, ValueError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=False,
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := OrderDraftSummaryScreen(
                OrderSummaryView(
                    service_name=summary_view.service_name,
                    duration_minutes=summary_view.duration_minutes,
                    objects_count=summary_view.objects_count,
                    service_amount=summary_view.service_amount,
                    platform_fee_amount=summary_view.platform_fee_amount,
                    total_amount=summary_view.total_amount,
                    performers_count=summary_view.performers_count,
                    location_label=summary_view.location_label,
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=False,
    )


@dataclass(frozen=True, slots=True)
class _DirectSelectionView:
    performer: PerformerView
    index: int
    total: int


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
    order_draft = draft(data)
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
        if profile is None:
            logger.warning(
                "Pool order publish requested without customer profile",
                extra={"telegram_id": telegram_user_context.telegram_id},
            )
            raise BackendClientError("Customer profile is missing")
        order_request = _order_request(OrderDraftSnapshot.from_data(order_draft))
        order = await backend_client.create_order_pool(
            customer_id=profile.id,
            service_id=order_request.service_id,
            start_at=order_request.start_at,
            end_at=order_request.end_at,
            care_object_ids=order_request.care_object_ids,
            address_id=order_request.address_id,
            location_source=order_request.location_source,
            customer_comment=order_request.customer_comment,
            report_photo_consent=order_request.report_photo_consent,
            option_values=order_request.option_values,
        )
    except BackendValidationError:
        logger.warning(
            "Backend rejected pool order publish",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to publish pool order",
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
    await state.clear()
    logger.info(
        "Pool order published",
        extra={
            "telegram_id": telegram_user_context.telegram_id,
            "order_id": str(order.id),
        },
    )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := OrderPublishedScreen(order).build()).text,
        reply_markup=screen.reply_markup,
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
    performer = await item_by_id(
        state,
        "order_performers",
        callback_data.performer_id,
        id_key="performer_id",
    )
    if performer is None:
        logger.warning(
            "Stale direct order performer callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "performer_id": str(callback_data.performer_id),
            },
        )
        await telegram_responder.acknowledge(callback)
        return
    data = await state.get_data()
    order_draft = draft(data)
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
        if profile is None:
            logger.warning(
                "Direct order publish requested without customer profile",
                extra={"telegram_id": telegram_user_context.telegram_id},
            )
            raise BackendClientError("Customer profile is missing")
        order_request = _order_request(OrderDraftSnapshot.from_data(order_draft))
        order = await backend_client.create_order_direct(
            customer_id=profile.id,
            service_id=order_request.service_id,
            start_at=order_request.start_at,
            end_at=order_request.end_at,
            care_object_ids=order_request.care_object_ids,
            address_id=order_request.address_id,
            location_source=order_request.location_source,
            customer_comment=order_request.customer_comment,
            report_photo_consent=order_request.report_photo_consent,
            option_values=order_request.option_values,
            performer_id=UUID(str(performer["performer_id"])),
        )
    except BackendValidationError:
        logger.warning(
            "Backend rejected direct order publish",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to publish direct order",
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
    await state.clear()
    logger.info(
        "Direct order published",
        extra={
            "telegram_id": telegram_user_context.telegram_id,
            "order_id": str(order.id),
        },
    )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := OrderPublishedScreen(order).build()).text,
        reply_markup=screen.reply_markup,
    )


@dataclass(frozen=True)
class _OrderRequest:
    service_id: UUID
    start_at: datetime
    end_at: datetime
    care_object_ids: tuple[UUID, ...]
    address_id: UUID | None
    location_source: str | None
    customer_comment: str | None
    report_photo_consent: bool | None
    option_values: dict[UUID, object]


def _order_request(snapshot: OrderDraftSnapshot) -> _OrderRequest:
    return _OrderRequest(
        service_id=snapshot.service_id,
        start_at=snapshot.start_at,
        end_at=snapshot.end_at,
        care_object_ids=snapshot.care_object_ids,
        address_id=snapshot.address_id,
        location_source=snapshot.location_source,
        customer_comment=snapshot.customer_comment,
        report_photo_consent=snapshot.report_photo_consent,
        option_values=snapshot.option_values,
    )

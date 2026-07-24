import logging
from datetime import datetime
from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    OrderAddressCallback,
    OrderCommentSkipCallback,
    OrderPhotoConsentCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.orders.state import (
    OrderCreation,
    OrderSummarySnapshot,
    draft,
    duration_unit,
    item_by_id,
    parse_duration_interval,
    performer_state,
    string_list,
)
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.types import YesNoValue
from customer_bot.presentation.ui.screens import (
    InvalidDurationScreen,
    OrderAddressStepScreen,
    OrderCommentStepScreen,
    OrderDraftSummaryScreen,
    OrderNoAddressesScreen,
    OrderPhotoConsentStepScreen,
    RetryLaterScreen,
    StaleActionScreen,
)
from customer_bot.presentation.view_models import OrderSummaryView

router = Router(name="orders_details")
logger = logging.getLogger(__name__)


@router.message(OrderCreation.duration)
async def enter_duration(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    order_draft = draft(data)
    duration = parse_duration_interval(message.text, order_draft)
    if duration is None:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=(
                screen := InvalidDurationScreen(duration_unit(order_draft)).build()
            ).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    start_at = datetime.fromisoformat(str(order_draft["start_at"]))
    end_at = start_at + duration
    order_draft["end_at"] = end_at.isoformat()
    await state.update_data(order_draft=order_draft)
    if order_draft.get("location_policy") != "customer_address":
        await _ask_photo_or_comment(
            message,
            bot,
            state,
            telegram_responder,
            telegram_user_context,
        )
        return
    try:
        addresses = await backend_client.list_addresses(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to load addresses for order",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    if not addresses:
        logger.info(
            "Order creation has no customer addresses",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := OrderNoAddressesScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    await state.set_state(OrderCreation.address)
    await state.update_data(
        order_addresses=[
            {
                "id": str(address.id),
                "address_text": address.address_text,
            }
            for address in addresses
        ],
    )
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := OrderAddressStepScreen(addresses).build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.callback_query(OrderCreation.address, OrderAddressCallback.filter())
async def select_address(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderAddressCallback,
) -> None:
    item = await item_by_id(state, "order_addresses", callback_data.address_id)
    if item is None:
        logger.warning(
            "Stale order address callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "address_id": str(callback_data.address_id),
            },
        )
        await telegram_responder.acknowledge(callback)
        return
    data = await state.get_data()
    order_draft = draft(data)
    order_draft["address_id"] = item["id"]
    await state.update_data(order_draft=order_draft)
    await _ask_photo_or_comment(
        callback,
        bot,
        state,
        telegram_responder,
        telegram_user_context,
    )


@router.callback_query(
    OrderCreation.photo_consent,
    OrderPhotoConsentCallback.filter(),
)
async def select_photo_consent(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderPhotoConsentCallback,
) -> None:
    value = callback_data.value
    data = await state.get_data()
    order_draft = draft(data)
    order_draft["report_photo_consent"] = value == YesNoValue.YES
    await state.set_state(OrderCreation.comment)
    await state.update_data(order_draft=order_draft)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := OrderCommentStepScreen().build()).text,
        reply_markup=screen.reply_markup,
    )


@router.message(OrderCreation.comment)
async def enter_comment(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    order_draft = draft(data)
    if message.text and message.text.strip():
        order_draft["customer_comment"] = message.text.strip()
    await _create_draft_and_show_summary(
        message,
        bot,
        state,
        backend_client,
        telegram_responder,
        telegram_user_context,
        order_draft,
    )


@router.callback_query(OrderCreation.comment, OrderCommentSkipCallback.filter())
async def skip_comment(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    await _create_draft_and_show_summary(
        callback,
        bot,
        state,
        backend_client,
        telegram_responder,
        telegram_user_context,
        draft(data),
    )


async def _ask_photo_or_comment(
    event: Message | CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    order_draft = draft(data)
    if order_draft.get("photo_policy") == "requires_customer_consent":
        await state.set_state(OrderCreation.photo_consent)
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := OrderPhotoConsentStepScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    order_draft["report_photo_consent"] = None
    await state.set_state(OrderCreation.comment)
    await state.update_data(order_draft=order_draft)
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := OrderCommentStepScreen().build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


async def _create_draft_and_show_summary(
    event: Message | CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    order_draft: dict[str, object],
) -> None:
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
        if profile is None:
            logger.warning(
                "Order summary requested without customer profile",
                extra={"telegram_id": telegram_user_context.telegram_id},
            )
            await telegram_responder.update(
                bot=bot,
                event=event,
                telegram_id=telegram_user_context.telegram_id,
                text=(screen := StaleActionScreen().build()).text,
                reply_markup=screen.reply_markup,
                create_new=True,
            )
            return
        start_at = datetime.fromisoformat(str(order_draft["start_at"]))
        end_at = datetime.fromisoformat(str(order_draft["end_at"]))
        care_object_ids = tuple(
            UUID(str(item)) for item in string_list(order_draft["care_object_ids"])
        )
        address_id = (
            UUID(str(order_draft["address_id"]))
            if order_draft.get("address_id")
            else None
        )
        objects_count = int(str(order_draft["objects_count"]))
        price = await backend_client.preview_order_price(
            customer_id=profile.id,
            service_id=UUID(str(order_draft["service_id"])),
            start_at=start_at,
            end_at=end_at,
            objects_count=objects_count,
        )
        performers = await backend_client.find_suitable_performers(
            city_id=profile.city_id,
            service_id=UUID(str(order_draft["service_id"])),
            start_at=start_at,
            end_at=end_at,
            objects_count=objects_count,
            care_object_ids=care_object_ids,
            address_id=address_id,
        )
    except BackendValidationError:
        logger.warning(
            "Backend rejected order order_draft preview",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to prepare order order_draft summary",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    await state.set_state(OrderCreation.publish)
    logger.info(
        "Order order_draft ready to publish",
        extra={
            "telegram_id": telegram_user_context.telegram_id,
            "performers_count": len(performers),
        },
    )
    summary = OrderSummarySnapshot(
        service_name=price.service_name,
        duration_minutes=price.duration_minutes,
        objects_count=price.objects_count,
        service_amount=price.service_amount,
        platform_fee_amount=price.platform_fee_amount,
        total_amount=price.total_amount,
        performers_count=len(performers),
        duration_unit=duration_unit(order_draft),
        start_at=start_at,
        end_at=end_at,
    )
    await state.update_data(
        order_draft=order_draft,
        order_performers=[performer_state(item) for item in performers],
        order_summary=summary.to_data(),
    )
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := OrderDraftSummaryScreen(
                OrderSummaryView(
                    service_name=summary.service_name,
                    duration_minutes=summary.duration_minutes,
                    objects_count=summary.objects_count,
                    service_amount=summary.service_amount,
                    platform_fee_amount=summary.platform_fee_amount,
                    total_amount=summary.total_amount,
                    performers_count=summary.performers_count,
                    duration_unit=summary.duration_unit,
                    start_at=summary.start_at,
                    end_at=summary.end_at,
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


__all__ = ["router"]

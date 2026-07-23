import logging
from datetime import date, datetime

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram_calendar import SimpleCalendarCallback

from customer_bot.presentation.callbacks import (
    OrderStartManualCallback,
    OrderStartTimeCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.orders.creation_navigation import (
    format_date,
    start_calendar,
    start_calendar_keyboard,
    start_time_value,
)
from customer_bot.presentation.handlers.orders.state import (
    OrderCreation,
    draft,
    duration_unit,
    parse_local_datetime,
    parse_local_time,
    start_is_valid,
)
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.screens import (
    InvalidDatetimeScreen,
    InvalidTimeScreen,
    OrderDatetimeManualStepScreen,
    OrderDurationStepScreen,
    OrderStartStepScreen,
    OrderStartTimeStepScreen,
    OrderTimeManualStepScreen,
)
from customer_bot.presentation.view_models import DateLabelView, DurationView

router = Router(name="orders_schedule")
logger = logging.getLogger(__name__)


@router.callback_query(OrderCreation.start, SimpleCalendarCallback.filter())
async def select_start_date(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: SimpleCalendarCallback,
) -> None:
    await _process_start_calendar_selection(
        callback,
        bot,
        state,
        telegram_responder,
        telegram_user_context,
        callback_data,
    )


async def _process_start_calendar_selection(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: SimpleCalendarCallback,
) -> None:
    selected, selected_date = await start_calendar().process_selection(
        callback,
        callback_data,
    )
    if not selected:
        return
    if not isinstance(selected_date, datetime):
        await telegram_responder.acknowledge(callback)
        return
    start_date = selected_date.date()
    await state.update_data(order_start_date=start_date.isoformat())
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := OrderStartTimeStepScreen(
                DateLabelView(date_label=format_date(start_date))
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.callback_query(OrderCreation.start, OrderStartManualCallback.filter())
async def request_manual_start(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderStartManualCallback,
) -> None:
    logger.info(
        "Order start manual requested",
        extra={
            "telegram_id": telegram_user_context.telegram_id,
            "mode": callback_data.mode,
            "state": await state.get_state(),
        },
    )
    data = await state.get_data()
    if callback_data.mode == "time":
        start_date = _start_date_from_state(data)
        if start_date is None:
            await telegram_responder.update(
                bot=bot,
                event=callback,
                telegram_id=telegram_user_context.telegram_id,
                text=(screen := OrderStartStepScreen().build()).text,
                reply_markup=await start_calendar_keyboard(),
                create_new=True,
            )
            return
        await state.update_data(order_start_manual_time=True)
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(
                screen := OrderTimeManualStepScreen(
                    DateLabelView(date_label=format_date(start_date))
                ).build()
            ).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    if callback_data.mode != "datetime":
        await telegram_responder.acknowledge(callback)
        return
    await state.update_data(order_start_manual_time=False)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := OrderDatetimeManualStepScreen().build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.callback_query(OrderCreation.start, OrderStartTimeCallback.filter())
async def select_start_time(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderStartTimeCallback,
) -> None:
    data = await state.get_data()
    start_date = _start_date_from_state(data)
    start_time = parse_local_time(start_time_value(callback_data.value))
    if start_date is None or start_time is None:
        await telegram_responder.acknowledge(callback)
        return
    await _set_start_at_and_ask_duration(
        callback,
        bot,
        state,
        telegram_responder,
        telegram_user_context,
        datetime.combine(start_date, start_time),
    )


@router.callback_query(SimpleCalendarCallback.filter())
async def stale_start_calendar(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: SimpleCalendarCallback,
) -> None:
    data = await state.get_data()
    if not draft(data):
        await telegram_responder.acknowledge(callback)
        return
    await state.set_state(OrderCreation.start)
    await _process_start_calendar_selection(
        callback,
        bot,
        state,
        telegram_responder,
        telegram_user_context,
        callback_data,
    )


@router.message(OrderCreation.start)
async def enter_start(
    message: Message,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    manual_time = data.get("order_start_manual_time") is True
    if not message.text:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=(
                screen := (
                    InvalidTimeScreen() if manual_time else InvalidDatetimeScreen()
                ).build()
            ).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    start_date = _start_date_from_state(data)
    if manual_time and start_date is not None:
        parsed_time = parse_local_time(message.text)
        start_at = (
            datetime.combine(start_date, parsed_time)
            if parsed_time is not None
            else None
        )
    else:
        start_at = parse_local_datetime(message.text)
    if start_at is None:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=(
                screen := (
                    InvalidTimeScreen() if manual_time else InvalidDatetimeScreen()
                ).build()
            ).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    if not start_is_valid(start_at):
        screen = InvalidDatetimeScreen().build()
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=screen.text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    await _set_start_at_and_ask_duration(
        message,
        bot,
        state,
        telegram_responder,
        telegram_user_context,
        start_at,
    )


async def _set_start_at_and_ask_duration(
    event: Message | CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    start_at: datetime,
) -> None:
    if not start_is_valid(start_at):
        screen = InvalidDatetimeScreen().build()
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text=screen.text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    data = await state.get_data()
    order_draft = draft(data)
    order_draft["start_at"] = start_at.isoformat()
    await state.set_state(OrderCreation.duration)
    await state.update_data(
        order_draft=order_draft,
        order_start_date=None,
        order_start_manual_time=False,
    )
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := OrderDurationStepScreen(
                DurationView(unit=duration_unit(order_draft))
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


def _start_date_from_state(data: dict[str, object]) -> date | None:
    raw_date = data.get("order_start_date")
    if not isinstance(raw_date, str):
        return None
    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        return None


__all__ = ["router"]

from datetime import time
from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from executor_bot.infrastructure.http import (
    BackendClient,
    BackendClientError,
    PerformerServiceDTO,
)
from executor_bot.presentation.callbacks import (
    AcceptingOrdersCallback,
    CalendarOpenCallback,
    CalendarScheduleCallback,
    CalendarUnavailableTomorrowCallback,
    ServiceLimitCallback,
    ServicesOpenCallback,
    ServiceToggleCallback,
)
from executor_bot.presentation.handlers.responses import send_step
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.services import TelegramResponder
from executor_bot.presentation.ui import (
    calendar_keyboard,
    calendar_text,
    calendar_updated_text,
    retry_later_text,
    services_keyboard,
    services_text,
    services_updated_text,
)

router = Router(name="services_calendar")


@router.callback_query(ServicesOpenCallback.filter())
async def open_services(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendClient,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        services = await backend_client.list_performer_services(
            telegram_id=telegram_user_context.telegram_id,
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
    await state.update_data(
        performer_services=[_service_state(item) for item in services],
    )
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=services_text(services),
        reply_markup=services_keyboard(services),
    )


@router.callback_query(AcceptingOrdersCallback.filter())
async def toggle_accepting_orders(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendClient,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: AcceptingOrdersCallback,
) -> None:
    try:
        await backend_client.set_accepting_orders(
            telegram_id=telegram_user_context.telegram_id,
            is_accepting_orders=callback_data.value,
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
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=services_updated_text(),
    )


@router.callback_query(ServiceToggleCallback.filter())
async def toggle_service(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendClient,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ServiceToggleCallback,
) -> None:
    item = await _service_by_index(state, callback_data.index)
    if item is None:
        return
    try:
        await backend_client.set_service_enabled(
            telegram_id=telegram_user_context.telegram_id,
            service_id=UUID(str(item["service_id"])),
            is_enabled=not bool(item["is_enabled"]),
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
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=services_updated_text(),
    )


@router.callback_query(ServiceLimitCallback.filter())
async def reduce_service_limit(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendClient,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ServiceLimitCallback,
) -> None:
    item = await _service_by_index(state, callback_data.index)
    if item is None:
        return
    raw_limit = item["performer_max_objects"]
    if not isinstance(raw_limit, int):
        return
    next_limit = max(1, raw_limit - 1)
    try:
        await backend_client.set_service_max_objects(
            telegram_id=telegram_user_context.telegram_id,
            service_id=UUID(str(item["service_id"])),
            performer_max_objects=next_limit,
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
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=services_updated_text(),
    )


@router.callback_query(CalendarOpenCallback.filter())
async def open_calendar(
    callback: CallbackQuery,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=calendar_text(),
        reply_markup=calendar_keyboard(),
    )


@router.callback_query(CalendarScheduleCallback.filter())
async def set_schedule(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendClient,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: CalendarScheduleCallback,
) -> None:
    try:
        await backend_client.set_schedule(
            telegram_id=telegram_user_context.telegram_id,
            schedule_type=callback_data.schedule_type,
            work_days=None,
            work_start_time=time(9),
            work_end_time=time(18),
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
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=calendar_updated_text(),
    )


@router.callback_query(CalendarUnavailableTomorrowCallback.filter())
async def add_unavailable_tomorrow(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendClient,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        await backend_client.add_tomorrow_unavailable(
            telegram_id=telegram_user_context.telegram_id,
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
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=calendar_updated_text(),
    )


async def _service_by_index(
    state: FSMContext,
    index: int,
) -> dict[str, object] | None:
    data = await state.get_data()
    services = data.get("performer_services")
    if not isinstance(services, list) or index < 0 or index >= len(services):
        return None
    item = services[index]
    return item if isinstance(item, dict) else None


def _service_state(item: PerformerServiceDTO) -> dict[str, object]:
    return {
        "service_id": str(item.service_id),
        "service_name": item.service_name,
        "is_enabled": item.is_enabled,
        "performer_max_objects": item.performer_max_objects,
    }


__all__ = ["router"]

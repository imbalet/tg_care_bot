from datetime import datetime, time
from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from executor_bot.application.dto import (
    CalendarDTO,
    CalendarOverrideDTO,
    PerformerServiceDTO,
)
from executor_bot.application.errors import BackendClientError, BackendValidationError
from executor_bot.application.ports import BackendPort
from executor_bot.presentation.callbacks import (
    AcceptingOrdersCallback,
    CalendarCancelUnavailableCallback,
    CalendarCustomScheduleCallback,
    CalendarOpenCallback,
    CalendarScheduleCallback,
    CalendarUnavailableCallback,
    NearbyOrderNotificationsCallback,
    ServiceLimitCallback,
    ServicesOpenCallback,
    ServiceToggleCallback,
)
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.services import TelegramResponder
from executor_bot.presentation.ui import (
    calendar_keyboard,
    calendar_updated_text,
    retry_later_text,
    services_keyboard,
    services_text,
    use_buttons_text,
)

router = Router(name="services_calendar")


class CalendarUnavailableForm(StatesGroup):
    period = State()


class CalendarCustomScheduleForm(StatesGroup):
    value = State()


@router.callback_query(ServicesOpenCallback.filter())
async def open_services(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        services = await backend_client.list_performer_services(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
        )
        return
    await _show_services(
        callback=callback,
        bot=bot,
        state=state,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        services=services,
    )


@router.callback_query(AcceptingOrdersCallback.filter())
async def toggle_accepting_orders(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: AcceptingOrdersCallback,
) -> None:
    try:
        await backend_client.set_accepting_orders(
            telegram_id=telegram_user_context.telegram_id,
            is_accepting_orders=callback_data.value,
        )
    except BackendValidationError:
        await telegram_responder.acknowledge(
            callback,
            "Сначала включите хотя бы одну одобренную услугу",
            show_alert=True,
        )
        return
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
        )
        return
    await _show_services(
        callback=callback,
        bot=bot,
        state=None,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
    )


@router.callback_query(NearbyOrderNotificationsCallback.filter())
async def toggle_nearby_order_notifications(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: NearbyOrderNotificationsCallback,
) -> None:
    try:
        await backend_client.set_nearby_order_notifications(
            telegram_id=telegram_user_context.telegram_id,
            is_enabled=callback_data.value,
        )
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
        )
        return
    await _show_services(
        callback=callback,
        bot=bot,
        state=state,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
    )


@router.callback_query(ServiceToggleCallback.filter())
async def toggle_service(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ServiceToggleCallback,
) -> None:
    item = await _service_by_index(state, callback_data.index)
    if item is None:
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    try:
        await backend_client.set_service_enabled(
            telegram_id=telegram_user_context.telegram_id,
            service_id=UUID(str(item["service_id"])),
            is_enabled=not bool(item["is_enabled"]),
        )
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
        )
        return
    await _show_services(
        callback=callback,
        bot=bot,
        state=state,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
    )


@router.callback_query(ServiceLimitCallback.filter())
async def reduce_service_limit(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ServiceLimitCallback,
) -> None:
    item = await _service_by_index(state, callback_data.index)
    if item is None:
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    raw_limit = item["performer_max_objects"]
    if not isinstance(raw_limit, int):
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    next_limit = max(1, raw_limit - 1)
    try:
        await backend_client.set_service_max_objects(
            telegram_id=telegram_user_context.telegram_id,
            service_id=UUID(str(item["service_id"])),
            performer_max_objects=next_limit,
        )
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
        )
        return
    await _show_services(
        callback=callback,
        bot=bot,
        state=state,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
    )


@router.callback_query(CalendarOpenCallback.filter())
async def open_calendar(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        calendar = await backend_client.get_calendar(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=_calendar_view(calendar),
        reply_markup=calendar_keyboard(_current_override(calendar)),
    )


@router.callback_query(CalendarScheduleCallback.filter())
async def set_schedule(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
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
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=calendar_updated_text(),
    )


@router.callback_query(CalendarCustomScheduleCallback.filter())
async def start_custom_schedule(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.set_state(CalendarCustomScheduleForm.value)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            "Введите рабочие дни и время:\n"
            "1–7 через запятую, затем интервал ЧЧ:ММ-ЧЧ:ММ.\n\n"
            "1,2,3,4,5 09:00-18:00\n"
            "(1 — понедельник, 7 — воскресенье)"
        ),
    )


@router.message(CalendarCustomScheduleForm.value)
async def save_custom_schedule(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    raw = (message.text or "").replace("–", "-")
    try:
        days_raw, times_raw = raw.split(maxsplit=1)
        days = tuple(sorted({int(item) for item in days_raw.split(",")}))
        start_raw, end_raw = times_raw.split("-", maxsplit=1)
        starts_at = time.fromisoformat(start_raw)
        ends_at = time.fromisoformat(end_raw)
        if not days or any(day < 1 or day > 7 for day in days):
            raise ValueError
        await backend_client.set_schedule(
            telegram_id=telegram_user_context.telegram_id,
            schedule_type="custom",
            work_days=days,
            work_start_time=starts_at,
            work_end_time=ends_at,
        )
    except ValueError, BackendValidationError:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Формат не распознан. Пример: 1,2,3,4,5 09:00-18:00",
        )
        return
    except BackendClientError:
        await state.clear()
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
        )
        return
    await state.clear()
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=calendar_updated_text(),
    )


@router.callback_query(CalendarUnavailableCallback.filter())
async def start_unavailable_period(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    state: FSMContext,
) -> None:
    await state.set_state(CalendarUnavailableForm.period)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            "Введите период недоступности одной строкой:\n"
            "ДД.ММ.ГГГГ ЧЧ:ММ — ДД.ММ.ГГГГ ЧЧ:ММ\n\n"
            "Например: 07.07.2026 10:00 — 10.07.2026 12:00"
        ),
    )


@router.message(CalendarUnavailableForm.period)
async def save_unavailable_period(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    raw = (message.text or "").replace("—", "-")
    parts = [part.strip() for part in raw.split("-")]
    if len(parts) != 2:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Не понял формат. Пример: 07.07.2026 10:00 — 10.07.2026 12:00",
        )
        return
    try:
        starts_at = datetime.strptime(parts[0], "%d.%m.%Y %H:%M")
        ends_at = datetime.strptime(parts[1], "%d.%m.%Y %H:%M")
        if starts_at >= ends_at:
            raise ValueError
        await backend_client.add_unavailable(
            telegram_id=telegram_user_context.telegram_id,
            starts_at=starts_at.isoformat(timespec="minutes"),
            ends_at=ends_at.isoformat(timespec="minutes"),
        )
    except ValueError, BackendValidationError:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=(
                "Период некорректен или уже есть запланированная недоступность. "
                "Проверьте даты и попробуйте снова."
            ),
        )
        return
    except BackendClientError:
        await state.clear()
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
        )
        return
    await state.clear()
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            "Недоступность запланирована. Она отображается в календаре "
            "и может быть отменена там."
        ),
    )


@router.callback_query(CalendarCancelUnavailableCallback.filter())
async def cancel_unavailable_period(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: CalendarCancelUnavailableCallback,
) -> None:
    try:
        await backend_client.cancel_unavailability(
            telegram_id=telegram_user_context.telegram_id,
            override_id=UUID(callback_data.override_id),
        )
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text="Недоступность отменена.",
    )


def _current_override(calendar: CalendarDTO) -> CalendarOverrideDTO | None:
    return next(
        (
            item
            for item in calendar.overrides
            if item.override_type == "unavailable" and item.is_active
        ),
        None,
    )


def _calendar_view(calendar: CalendarDTO) -> str:
    schedule = "График не задан"
    if calendar.schedule is not None:
        schedule = (
            f"{calendar.schedule.schedule_type}: "
            f"{calendar.schedule.work_start_time[:5]}–"
            f"{calendar.schedule.work_end_time[:5]}"
        )
    lines = ["<b>Календарь исполнителя</b>", "", f"График: {schedule}"]
    override = _current_override(calendar)
    if override is None:
        lines.append("Недоступность: нет")
    else:
        status = (
            "сейчас действует"
            if override.starts_at
            <= datetime.now(override.starts_at.tzinfo)
            < override.ends_at
            else "запланирована"
        )
        lines.append(
            f"Недоступность ({status}): {override.starts_at:%d.%m.%Y %H:%M} — "
            f"{override.ends_at:%d.%m.%Y %H:%M}"
        )
    if calendar.busy_intervals:
        lines.extend(["", "Занятые интервалы:"])
        lines.extend(
            f"• {item.starts_at:%d.%m %H:%M}–{item.ends_at:%H:%M} · {item.kind}"
            for item in calendar.busy_intervals[:8]
        )
    return "\n".join(lines)


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


async def _show_services(
    *,
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext | None,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    services: tuple[PerformerServiceDTO, ...] | None = None,
) -> None:
    services = services or await backend_client.list_performer_services(
        telegram_id=telegram_user_context.telegram_id,
    )
    registration = await backend_client.get_registration_state(
        telegram_user_context.telegram_id,
    )
    nearby_notifications_enabled = await backend_client.get_nearby_order_notifications(
        telegram_id=telegram_user_context.telegram_id,
    )
    is_accepting_orders = bool(
        registration.performer and registration.performer.is_accepting_orders
    )
    if state is not None:
        await state.update_data(
            performer_services=[_service_state(item) for item in services],
            is_accepting_orders=is_accepting_orders,
            nearby_notifications_enabled=nearby_notifications_enabled,
        )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=services_text(
            services,
            is_accepting_orders,
            nearby_notifications_enabled,
        ),
        reply_markup=services_keyboard(
            services,
            is_accepting_orders=is_accepting_orders,
            nearby_notifications_enabled=nearby_notifications_enabled,
        ),
    )


def _service_state(item: PerformerServiceDTO) -> dict[str, object]:
    return {
        "service_id": str(item.service_id),
        "service_name": item.service_name,
        "is_enabled": item.is_enabled,
        "performer_max_objects": item.performer_max_objects,
    }


__all__ = ["router"]

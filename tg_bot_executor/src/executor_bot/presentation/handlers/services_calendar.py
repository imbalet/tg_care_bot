import re
from datetime import date, datetime, time
from typing import cast
from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback

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
    ServicesOpenCallback,
    ServiceToggleCallback,
)
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.services import TelegramResponder
from executor_bot.presentation.ui import (
    calendar_keyboard,
    retry_later_text,
    services_keyboard,
    services_text,
    use_buttons_text,
)

router = Router(name="services_calendar")


class CalendarUnavailableForm(StatesGroup):
    start_date = State()
    end_date = State()
    start_time = State()
    end_time = State()


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
            reply_markup=services_keyboard(()),
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
    except BackendValidationError as exc:
        error_text = (
            "Сначала добавьте и выберите рабочий адрес."
            if "address" in str(exc).lower() or "адрес" in str(exc).lower()
            else "Сначала включите хотя бы одну одобренную услугу"
        )
        await telegram_responder.acknowledge(
            callback,
            error_text,
            show_alert=True,
        )
        return
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
            reply_markup=services_keyboard(()),
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
            reply_markup=services_keyboard(()),
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
            reply_markup=services_keyboard(()),
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
            reply_markup=calendar_keyboard(),
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
            reply_markup=calendar_keyboard(),
        )
        return
    await _show_calendar(
        event=callback,
        bot=bot,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
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
            reply_markup=calendar_keyboard(),
        )
        return
    await state.clear()
    await _show_calendar(
        event=message,
        bot=bot,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
    )


@router.callback_query(CalendarUnavailableCallback.filter())
async def start_unavailable_period(
    callback: CallbackQuery,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    state: FSMContext,
) -> None:
    await state.set_state(CalendarUnavailableForm.start_date)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text="Выберите дату начала недоступности.",
        reply_markup=await _unavailable_calendar_keyboard(),
    )


@router.callback_query(
    CalendarUnavailableForm.start_date,
    SimpleCalendarCallback.filter(),
)
async def select_unavailable_start_date(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: SimpleCalendarCallback,
) -> None:
    selected_date = await _process_calendar_selection(callback, callback_data)
    if selected_date is None:
        return
    await state.update_data(unavailable_start_date=selected_date.isoformat())
    await state.set_state(CalendarUnavailableForm.end_date)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            f"Дата начала: {selected_date:%d.%m.%Y}\n\n"
            "Выберите дату окончания недоступности."
        ),
        reply_markup=await _unavailable_calendar_keyboard(),
    )


@router.callback_query(
    CalendarUnavailableForm.end_date,
    SimpleCalendarCallback.filter(),
)
async def select_unavailable_end_date(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: SimpleCalendarCallback,
) -> None:
    selected_date = await _process_calendar_selection(callback, callback_data)
    if selected_date is None:
        return
    data = await state.get_data()
    start_date = _stored_date(data.get("unavailable_start_date"))
    if start_date is None or selected_date < start_date:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text="Дата окончания не может быть раньше даты начала. Выберите снова.",
            reply_markup=await _unavailable_calendar_keyboard(),
        )
        return
    await state.update_data(unavailable_end_date=selected_date.isoformat())
    await state.set_state(CalendarUnavailableForm.start_time)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text="Введите время начала недоступности в формате ЧЧ:ММ.",
        create_new=True,
    )


@router.message(CalendarUnavailableForm.start_time)
async def save_unavailable_start_time(
    message: Message,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    parsed = _parse_time(message.text)
    if parsed is None:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Введите время в формате ЧЧ:ММ, например 09:30.",
            create_new=True,
        )
        return
    await state.update_data(unavailable_start_time=parsed.isoformat(timespec="minutes"))
    await state.set_state(CalendarUnavailableForm.end_time)
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text="Введите время окончания недоступности в формате ЧЧ:ММ.",
        create_new=True,
    )


@router.message(CalendarUnavailableForm.end_time)
async def save_unavailable_end_time(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    parsed = _parse_time(message.text)
    if parsed is None:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Введите время в формате ЧЧ:ММ, например 18:00.",
            create_new=True,
        )
        return
    data = await state.get_data()
    start_date = _stored_date(data.get("unavailable_start_date"))
    end_date = _stored_date(data.get("unavailable_end_date"))
    start_time = _parse_time(data.get("unavailable_start_time"))
    if start_date is None or end_date is None or start_time is None:
        await state.clear()
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
            reply_markup=calendar_keyboard(),
        )
        return
    starts_at = datetime.combine(start_date, start_time)
    ends_at = datetime.combine(end_date, parsed)
    if starts_at >= ends_at:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Окончание должно быть позже начала. Введите время окончания снова.",
            create_new=True,
        )
        return
    try:
        await backend_client.add_unavailable(
            telegram_id=telegram_user_context.telegram_id,
            starts_at=starts_at.isoformat(timespec="minutes"),
            ends_at=ends_at.isoformat(timespec="minutes"),
        )
    except BackendValidationError:
        await state.set_state(CalendarUnavailableForm.end_time)
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=(
                "Период некорректен или уже есть запланированная недоступность. "
                "Введите время окончания снова."
            ),
            create_new=True,
        )
        return
    except BackendClientError:
        await state.set_state(CalendarUnavailableForm.end_time)
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=(
                f"{retry_later_text()}\n\n"
                "Введите время окончания недоступности ещё раз."
            ),
            create_new=True,
        )
        return
    await state.clear()
    await _show_calendar(
        event=message,
        bot=bot,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        create_new=True,
    )


async def _unavailable_calendar_keyboard() -> InlineKeyboardMarkup:
    return cast(InlineKeyboardMarkup, await SimpleCalendar().start_calendar())


async def _process_calendar_selection(
    callback: CallbackQuery,
    callback_data: SimpleCalendarCallback,
) -> date | None:
    selected, selected_date = await SimpleCalendar().process_selection(
        callback,
        callback_data,
    )
    if not selected or not isinstance(selected_date, datetime):
        return None
    return selected_date.date()


def _stored_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_time(value: object) -> time | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value) is None:
        return None
    try:
        parsed = time.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return None
    return parsed


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
            reply_markup=calendar_keyboard(),
        )
        return
    await _show_calendar(
        event=callback,
        bot=bot,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
    )


async def _show_calendar(
    *,
    event: Message | CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_id: int,
    create_new: bool = False,
) -> None:
    try:
        calendar = await backend_client.get_calendar(telegram_id=telegram_id)
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_id,
            text=retry_later_text(),
            reply_markup=calendar_keyboard(),
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_id,
        text=_calendar_view(calendar),
        reply_markup=calendar_keyboard(_current_override(calendar)),
        create_new=create_new,
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
        schedule_name = _schedule_name(calendar.schedule)
        schedule = (
            f"{schedule_name}, "
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
            f"• {item.starts_at:%d.%m %H:%M}–{item.ends_at:%H:%M} · "
            f"{_busy_interval_name(item.kind)}"
            for item in calendar.busy_intervals[:8]
        )
    return "\n".join(lines)


def _schedule_name(schedule: object) -> str:
    schedule_type = getattr(schedule, "schedule_type", "")
    names = {
        "every_day": "каждый день",
        "weekdays": "будни",
        "weekends": "выходные",
        "custom": "выбранные дни",
    }
    name = names.get(schedule_type, "выбранные дни")
    work_days = getattr(schedule, "work_days", None)
    if schedule_type == "custom" and isinstance(work_days, tuple):
        day_names = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
        selected = [
            day_names[day - 1]
            for day in work_days
            if isinstance(day, int) and 1 <= day <= len(day_names)
        ]
        if selected:
            name = ", ".join(selected)
    return name


def _busy_interval_name(kind: str) -> str:
    return {
        "direct": "direct-заказ",
        "response": "отклик",
        "order": "назначенный заказ",
    }.get(kind, "занятый интервал")


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

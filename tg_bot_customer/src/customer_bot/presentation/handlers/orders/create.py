import logging
from datetime import date, datetime
from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram_calendar import SimpleCalendarCallback

from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import ActiveCategoryStore, BackendPort
from customer_bot.presentation.callbacks import (
    OrderAddAddressCallback,
    OrderAddObjectCallback,
    OrderAddressCallback,
    OrderCommentSkipCallback,
    OrderCreateCallback,
    OrderObjectCallback,
    OrderObjectsDoneCallback,
    OrderPhotoConsentCallback,
    OrderServiceCallback,
    OrderStartManualCallback,
    OrderStartTimeCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.addresses.state import AddressManagement
from customer_bot.presentation.handlers.care_objects.state import CareObjectManagement
from customer_bot.presentation.handlers.orders.state import (
    LOCAL_TZ,
    OrderCreation,
)
from customer_bot.presentation.handlers.orders.state import (
    care_object_state as _care_object_state,
)
from customer_bot.presentation.handlers.orders.state import (
    draft as _draft,
)
from customer_bot.presentation.handlers.orders.state import (
    item_by_index as _item_by_index,
)
from customer_bot.presentation.handlers.orders.state import (
    parse_duration_interval as _parse_duration_interval,
)
from customer_bot.presentation.handlers.orders.state import (
    parse_local_datetime as _parse_local_datetime,
)
from customer_bot.presentation.handlers.orders.state import (
    parse_local_time as _parse_local_time,
)
from customer_bot.presentation.handlers.orders.state import (
    performer_state as _performer_state,
)
from customer_bot.presentation.handlers.orders.state import (
    selected_ids as _selected_ids,
)
from customer_bot.presentation.handlers.orders.state import (
    service_states as _service_states,
)
from customer_bot.presentation.handlers.orders.state import (
    string_list as _string_list,
)
from customer_bot.presentation.handlers.orders.state import (
    uses_days as _uses_days,
)
from customer_bot.presentation.handlers.responses import send_step
from customer_bot.presentation.navigation import active_category
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.types import YesNoValue
from customer_bot.presentation.ui import (
    address_city_keyboard,
    address_city_step_text,
    invalid_datetime_text,
    invalid_duration_text,
    invalid_time_text,
    order_address_step_text,
    order_addresses_keyboard,
    order_comment_skip_keyboard,
    order_comment_step_text,
    order_datetime_manual_step_text,
    order_draft_summary_text,
    order_duration_step_text,
    order_no_addresses_keyboard,
    order_no_addresses_text,
    order_no_objects_keyboard,
    order_no_objects_text,
    order_no_services_text,
    order_objects_keyboard,
    order_objects_step_text,
    order_photo_consent_keyboard,
    order_photo_consent_step_text,
    order_publish_keyboard,
    order_services_keyboard,
    order_services_step_text,
    order_start_calendar,
    order_start_calendar_keyboard,
    order_start_step_text,
    order_start_time_keyboard,
    order_start_time_step_text,
    order_time_manual_step_text,
    retry_later_text,
    use_buttons_text,
    validation_error_text,
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
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    if category is None:
        logger.warning(
            "Order creation requested without active category",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=use_buttons_text(),
        )
        return
    services = _service_states((category,))
    if not services:
        logger.warning(
            "Order creation category has no services",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "category_code": category.code,
            },
        )
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=order_no_services_text(),
        )
        return
    await state.set_state(OrderCreation.service)
    await state.update_data(
        order_services=services,
        order_draft={
            "category_code": category.code,
            "category_name": category.name,
            "care_object_type": category.care_object_type,
        },
    )
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_services_step_text(),
        reply_markup=order_services_keyboard(services),
    )


@router.callback_query(OrderCreation.service, OrderServiceCallback.filter())
async def select_service(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderServiceCallback,
) -> None:
    service = await _item_by_index(state, "order_services", callback_data.index)
    if service is None:
        logger.warning(
            "Stale order service callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": callback_data.index,
            },
        )
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    draft = _draft(await state.get_data())
    draft.update(
        {
            "service_id": service["id"],
            "service_name": service["name"],
            "care_object_type": service["care_object_type"],
            "max_objects_per_order": service["max_objects_per_order"],
            "price_type": service["price_type"],
            "allows_multiday": service["allows_multiday"],
            "min_duration_minutes": service["min_duration_minutes"],
            "max_duration_minutes": service["max_duration_minutes"],
            "duration_step_minutes": service["duration_step_minutes"],
            "location_policy": service["location_policy"],
            "photo_policy": service["photo_policy"],
        },
    )
    try:
        objects = await backend_client.list_care_objects(
            telegram_id=telegram_user_context.telegram_id,
            object_type=str(service["care_object_type"]),
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to load care objects for order",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "service_id": str(service["id"]),
                "exception_type": type(exc).__name__,
            },
        )
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    if not objects:
        logger.info(
            "Order creation has no care objects",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "care_object_type": str(service["care_object_type"]),
            },
        )
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=order_no_objects_text(str(service["care_object_type"])),
            reply_markup=order_no_objects_keyboard(),
        )
        return
    await state.set_state(OrderCreation.object)
    draft["care_object_ids"] = []
    draft["objects_count"] = 0
    await state.update_data(
        order_draft=draft,
        order_objects=[_care_object_state(item) for item in objects],
    )
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_objects_step_text(
            selected_count=0,
            max_count=int(str(service["max_objects_per_order"])),
        ),
        reply_markup=order_objects_keyboard(
            objects,
            selected_ids=(),
            can_finish=False,
        ),
    )


@router.callback_query(OrderCreation.object, OrderObjectCallback.filter())
async def select_object(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderObjectCallback,
) -> None:
    item = await _item_by_index(state, "order_objects", callback_data.index)
    if item is None:
        logger.warning(
            "Stale order object callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": callback_data.index,
            },
        )
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    data = await state.get_data()
    draft = _draft(data)
    selected = _selected_ids(data)
    item_id = str(item["id"])
    if item_id in selected:
        selected.remove(item_id)
    else:
        max_objects = int(str(draft.get("max_objects_per_order", 1)))
        if len(selected) >= max_objects:
            await telegram_responder.acknowledge(
                callback,
                f"Можно выбрать не больше {max_objects}.",
            )
            return
        selected.append(item_id)
    draft["care_object_ids"] = selected
    draft["objects_count"] = len(selected)
    max_objects = int(str(draft.get("max_objects_per_order", 1)))
    await state.update_data(order_draft=draft)
    if max_objects <= 1 and selected:
        await _ask_start_at(
            callback, bot, state, telegram_responder, telegram_user_context
        )
        return
    objects = data.get("order_objects")
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_objects_step_text(
            selected_count=len(selected),
            max_count=max_objects,
        ),
        reply_markup=order_objects_keyboard(
            objects if isinstance(objects, list) else (),
            selected_ids=selected,
            can_finish=bool(selected),
        ),
    )


@router.callback_query(OrderCreation.object, OrderObjectsDoneCallback.filter())
async def finish_object_selection(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    if not _selected_ids(data):
        await telegram_responder.acknowledge(
            callback, "Выберите хотя бы одну карточку."
        )
        return
    await _ask_start_at(callback, bot, state, telegram_responder, telegram_user_context)


async def _ask_start_at(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.set_state(OrderCreation.start)
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_start_step_text(),
        reply_markup=await order_start_calendar_keyboard(),
    )


@router.callback_query(OrderCreation.start, SimpleCalendarCallback.filter())
async def select_start_date(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: SimpleCalendarCallback,
) -> None:
    selected, selected_date = await order_start_calendar().process_selection(
        callback,
        callback_data,
    )
    if not selected:
        return
    if not isinstance(selected_date, datetime):
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    start_date = selected_date.date()
    await state.update_data(order_start_date=start_date.isoformat())
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_start_time_step_text(_format_date(start_date)),
        reply_markup=order_start_time_keyboard(),
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
    data = await state.get_data()
    if callback_data.mode == "time":
        start_date = _start_date_from_state(data)
        if start_date is None:
            await send_step(
                bot=bot,
                event=callback,
                telegram_responder=telegram_responder,
                telegram_user_context=telegram_user_context,
                text=order_start_step_text(),
                reply_markup=await order_start_calendar_keyboard(),
            )
            return
        await state.update_data(order_start_manual_time=True)
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=order_time_manual_step_text(_format_date(start_date)),
        )
        return
    await state.update_data(order_start_manual_time=False)
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_datetime_manual_step_text(),
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
    start_time = _parse_local_time(callback_data.value)
    if start_date is None or start_time is None:
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    await _set_start_at_and_ask_duration(
        callback,
        bot,
        state,
        telegram_responder,
        telegram_user_context,
        datetime.combine(start_date, start_time, tzinfo=LOCAL_TZ),
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
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=invalid_time_text() if manual_time else invalid_datetime_text(),
        )
        return
    start_date = _start_date_from_state(data)
    if manual_time and start_date is not None:
        parsed_time = _parse_local_time(message.text)
        start_at = (
            datetime.combine(start_date, parsed_time, tzinfo=LOCAL_TZ)
            if parsed_time is not None
            else None
        )
    else:
        start_at = _parse_local_datetime(message.text)
    if start_at is None:
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=invalid_time_text() if manual_time else invalid_datetime_text(),
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
    data = await state.get_data()
    draft = _draft(data)
    draft["start_at"] = start_at.isoformat()
    await state.set_state(OrderCreation.duration)
    await state.update_data(
        order_draft=draft,
        order_start_date=None,
        order_start_manual_time=False,
    )
    await send_step(
        bot=bot,
        event=event,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_duration_step_text(uses_days=_uses_days(draft)),
    )


def _start_date_from_state(data: dict[str, object]) -> date | None:
    raw_date = data.get("order_start_date")
    if not isinstance(raw_date, str):
        return None
    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        return None


def _format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


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
    draft = _draft(data)
    duration = _parse_duration_interval(message.text, draft)
    if duration is None:
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=invalid_duration_text(uses_days=_uses_days(draft)),
        )
        return
    start_at = datetime.fromisoformat(str(draft["start_at"]))
    end_at = start_at + duration
    draft["end_at"] = end_at.isoformat()
    await state.update_data(order_draft=draft)
    if draft.get("location_policy") != "customer_address":
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
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    if not addresses:
        logger.info(
            "Order creation has no customer addresses",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=order_no_addresses_text(),
            reply_markup=order_no_addresses_keyboard(),
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
    await send_step(
        bot=bot,
        event=message,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_address_step_text(),
        reply_markup=order_addresses_keyboard(addresses),
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
    item = await _item_by_index(state, "order_addresses", callback_data.index)
    if item is None:
        logger.warning(
            "Stale order address callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": callback_data.index,
            },
        )
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    data = await state.get_data()
    draft = _draft(data)
    draft["address_id"] = item["id"]
    await state.update_data(order_draft=draft)
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
    draft = _draft(data)
    draft["report_photo_consent"] = value == YesNoValue.YES
    await state.set_state(OrderCreation.comment)
    await state.update_data(order_draft=draft)
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_comment_step_text(),
        reply_markup=order_comment_skip_keyboard(),
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
    draft = _draft(data)
    if message.text and message.text.strip():
        draft["customer_comment"] = message.text.strip()
    await _create_draft_and_show_summary(
        message,
        bot,
        state,
        backend_client,
        telegram_responder,
        telegram_user_context,
        draft,
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
        _draft(data),
    )


async def _ask_photo_or_comment(
    event: Message | CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    draft = _draft(data)
    if draft.get("photo_policy") == "requires_customer_consent":
        await state.set_state(OrderCreation.photo_consent)
        await send_step(
            bot=bot,
            event=event,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=order_photo_consent_step_text(),
            reply_markup=order_photo_consent_keyboard(),
        )
        return
    draft["report_photo_consent"] = None
    await state.set_state(OrderCreation.comment)
    await state.update_data(order_draft=draft)
    await send_step(
        bot=bot,
        event=event,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_comment_step_text(),
        reply_markup=order_comment_skip_keyboard(),
    )


async def _create_draft_and_show_summary(
    event: Message | CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    draft: dict[str, object],
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
            await send_step(
                bot=bot,
                event=event,
                telegram_responder=telegram_responder,
                telegram_user_context=telegram_user_context,
                text=use_buttons_text(),
            )
            return
        start_at = datetime.fromisoformat(str(draft["start_at"]))
        end_at = datetime.fromisoformat(str(draft["end_at"]))
        care_object_ids = tuple(
            UUID(str(item)) for item in _string_list(draft["care_object_ids"])
        )
        address_id = UUID(str(draft["address_id"])) if draft.get("address_id") else None
        objects_count = int(str(draft["objects_count"]))
        price = await backend_client.preview_order_price(
            service_id=UUID(str(draft["service_id"])),
            start_at=start_at,
            end_at=end_at,
            objects_count=objects_count,
        )
        performers = await backend_client.find_suitable_performers(
            city_id=profile.city_id,
            service_id=UUID(str(draft["service_id"])),
            start_at=start_at,
            end_at=end_at,
            objects_count=objects_count,
            care_object_ids=care_object_ids,
            address_id=address_id,
        )
    except BackendValidationError as exc:
        logger.warning(
            "Backend rejected order draft preview",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await send_step(
            bot=bot,
            event=event,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=validation_error_text(str(exc)),
        )
        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to prepare order draft summary",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await send_step(
            bot=bot,
            event=event,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await state.set_state(OrderCreation.publish)
    logger.info(
        "Order draft ready to publish",
        extra={
            "telegram_id": telegram_user_context.telegram_id,
            "performers_count": len(performers),
        },
    )
    await state.update_data(
        order_draft=draft,
        order_performers=[_performer_state(item) for item in performers],
    )
    await send_step(
        bot=bot,
        event=event,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_draft_summary_text(price=price, performers_count=len(performers)),
        reply_markup=order_publish_keyboard(performers),
    )


@router.callback_query(OrderCreation.object, OrderAddObjectCallback.filter())
async def add_order_object(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    draft = _draft(data)
    await state.update_data(
        return_to_order_after_care_object=True,
        draft={"object_type": str(draft["care_object_type"])},
        order_draft=draft,
    )
    await state.set_state(CareObjectManagement.name)
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text="Введите имя или короткое название.",
    )


@router.callback_query(OrderCreation.address, OrderAddAddressCallback.filter())
async def add_order_address(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        cities = await backend_client.list_active_cities()
    except BackendClientError as exc:
        logger.warning(
            "Failed to load cities for order address creation",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await state.update_data(
        return_to_order_after_address=True,
        city_ids=[str(city.id) for city in cities],
        city_names=[city.name for city in cities],
        address_draft={},
    )
    await state.set_state(AddressManagement.city)
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=address_city_step_text(),
        reply_markup=address_city_keyboard(cities),
    )

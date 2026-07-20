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
    OrderOptionsDoneCallback,
    OrderOptionToggleCallback,
    OrderPhotoConsentCallback,
    OrderServiceCallback,
    OrderStartManualCallback,
    OrderStartTimeCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.addresses.state import AddressManagement
from customer_bot.presentation.handlers.care_objects.state import CareObjectManagement
from customer_bot.presentation.handlers.orders.creation_navigation import (
    format_date,
    start_calendar,
    start_calendar_keyboard,
    start_time_value,
)
from customer_bot.presentation.handlers.orders.creation_views import service_view
from customer_bot.presentation.handlers.orders.state import (
    OrderCreation,
    care_object_state,
    draft,
    duration_unit,
    item_by_id,
    parse_duration_interval,
    parse_local_datetime,
    parse_local_time,
    performer_state,
    selected_ids,
    service_states,
    string_list,
)
from customer_bot.presentation.navigation import active_category
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.types import YesNoValue
from customer_bot.presentation.ui.screens import (
    AddressCityStepScreen,
    CareObjectNameStepScreen,
    InvalidDatetimeScreen,
    InvalidDurationScreen,
    InvalidTimeScreen,
    OrderAddressStepScreen,
    OrderCommentStepScreen,
    OrderDatetimeManualStepScreen,
    OrderDraftSummaryScreen,
    OrderDurationStepScreen,
    OrderNoAddressesScreen,
    OrderNoObjectsScreen,
    OrderNoServicesScreen,
    OrderObjectsStepScreen,
    OrderOptionsStepScreen,
    OrderPhotoConsentStepScreen,
    OrderServicesStepScreen,
    OrderStartStepScreen,
    OrderStartTimeStepScreen,
    OrderTimeManualStepScreen,
    RetryLaterScreen,
    StaleActionScreen,
)
from customer_bot.presentation.view_models import (
    DateLabelView,
    DurationView,
    ObjectNameView,
    ObjectsStepView,
    ObjectTypeView,
    OptionsStepView,
    OrderSummaryView,
    SelectableObjectView,
    SelectableOptionView,
    ServicesView,
)

router = Router(name="orders_create")
logger = logging.getLogger(__name__)

CARE_OBJECT_TYPE_LABELS = {
    "child": "Ребенок",
    "ward": "Подопечный",
    "pet": "Питомец",
}


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
            create_new=True,
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
            create_new=True,
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
            create_new=True,
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
        create_new=True,
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
    service = await item_by_id(state, "order_services", callback_data.service_id)
    if service is None:
        logger.warning(
            "Stale order service callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "service_id": str(callback_data.service_id),
            },
        )
        await telegram_responder.acknowledge(callback)
        return
    order_draft = draft(await state.get_data())
    order_draft.update(
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
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
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
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(
                screen := OrderNoObjectsScreen(
                    ObjectTypeView(object_type=str(service["care_object_type"]))
                ).build()
            ).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    await state.set_state(OrderCreation.object)
    order_draft["care_object_ids"] = []
    order_draft["objects_count"] = 0
    await state.update_data(
        order_draft=order_draft,
        order_objects=[care_object_state(item) for item in objects],
    )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := OrderObjectsStepScreen(
                ObjectsStepView(
                    max_count=int(str(service["max_objects_per_order"])),
                    selected_count=0,
                    selected_ids=(),
                    items=tuple(
                        SelectableObjectView(
                            id=str(item.id), display_name=item.display_name
                        )
                        for item in objects
                    ),
                    can_finish=False,
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
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
    item = await item_by_id(state, "order_objects", callback_data.care_object_id)
    if item is None:
        logger.warning(
            "Stale order object callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "care_object_id": str(callback_data.care_object_id),
            },
        )
        await telegram_responder.acknowledge(callback)
        return
    data = await state.get_data()
    order_draft = draft(data)
    selected = selected_ids(data)
    item_id = str(item["id"])
    if item_id in selected:
        selected.remove(item_id)
    else:
        max_objects = int(str(order_draft.get("max_objects_per_order", 1)))
        if len(selected) >= max_objects:
            await telegram_responder.acknowledge(
                callback,
                f"Можно выбрать не больше {max_objects}.",
            )
            return
        selected.append(item_id)
    order_draft["care_object_ids"] = selected
    order_draft["objects_count"] = len(selected)
    max_objects = int(str(order_draft.get("max_objects_per_order", 1)))
    await state.update_data(order_draft=order_draft)
    if max_objects <= 1 and selected:
        await _ask_options_or_start(
            callback, bot, state, telegram_responder, telegram_user_context
        )
        return
    objects = data.get("order_objects")
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := OrderObjectsStepScreen(
                ObjectsStepView(
                    max_count=max_objects,
                    selected_count=len(selected),
                    selected_ids=tuple(selected),
                    items=tuple(
                        SelectableObjectView(
                            id=str(item.get("id", "")),
                            display_name=str(item.get("display_name", "")),
                        )
                        for item in (objects if isinstance(objects, list) else ())
                        if isinstance(item, dict)
                    ),
                    can_finish=bool(selected),
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
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
    if not selected_ids(data):
        await telegram_responder.acknowledge(callback)
        return
    await _ask_options_or_start(
        callback,
        bot,
        state,
        telegram_responder,
        telegram_user_context,
    )


async def _ask_options_or_start(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    order_draft = draft(data)
    options = order_draft.get("options")
    if isinstance(options, list) and options:
        await state.set_state(OrderCreation.options)
        await state.update_data(order_options=options)
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(
                screen := OrderOptionsStepScreen(
                    OptionsStepView(
                        selected_count=0,
                        selected_ids=(),
                        items=tuple(
                            SelectableOptionView(
                                id=str(item.get("id", "")),
                                name=str(item.get("name", "")),
                            )
                            for item in options
                            if isinstance(item, dict)
                        ),
                        can_finish=True,
                    )
                ).build()
            ).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    order_draft["option_values"] = {}
    await state.update_data(order_draft=order_draft)
    await _ask_start_at(callback, bot, state, telegram_responder, telegram_user_context)


@router.callback_query(OrderCreation.options, OrderOptionToggleCallback.filter())
async def toggle_option(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderOptionToggleCallback,
) -> None:
    item = await item_by_id(state, "order_options", callback_data.option_id)
    if item is None:
        await telegram_responder.acknowledge(callback)
        return
    data = await state.get_data()
    order_draft = draft(data)
    selected = string_list(order_draft.get("selected_option_ids"))
    item_id = str(item["id"])
    if item_id in selected:
        selected.remove(item_id)
    else:
        selected.append(item_id)
    order_draft["selected_option_ids"] = selected
    options = order_draft.get("options")
    await state.update_data(order_draft=order_draft)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := OrderOptionsStepScreen(
                OptionsStepView(
                    selected_count=len(selected),
                    selected_ids=tuple(selected),
                    items=tuple(
                        SelectableOptionView(
                            id=str(item.get("id", "")),
                            name=str(item.get("name", "")),
                        )
                        for item in (options if isinstance(options, list) else ())
                        if isinstance(item, dict)
                    ),
                    can_finish=True,
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.callback_query(OrderCreation.options, OrderOptionsDoneCallback.filter())
async def finish_options(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    order_draft = draft(data)
    options = order_draft.get("options")
    selected = set(string_list(order_draft.get("selected_option_ids")))
    option_values = {}
    if isinstance(options, list):
        option_values = {
            str(option["id"]): True
            for option in options
            if isinstance(option, dict) and str(option.get("id")) in selected
        }
    order_draft["option_values"] = option_values
    await state.update_data(order_draft=order_draft)
    await _ask_start_at(callback, bot, state, telegram_responder, telegram_user_context)


async def _ask_start_at(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.set_state(OrderCreation.start)
    await state.update_data(
        order_start_date=None,
        order_start_manual_time=False,
    )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=OrderStartStepScreen().build().text,
        reply_markup=await start_calendar_keyboard(),
        create_new=True,
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
        create_new=True,
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
    await state.update_data(
        order_draft=order_draft,
        order_performers=[performer_state(item) for item in performers],
        order_summary={
            "service_name": price.service_name,
            "duration_minutes": price.duration_minutes,
            "objects_count": price.objects_count,
            "service_amount": str(price.service_amount),
            "platform_fee_amount": str(price.platform_fee_amount),
            "total_amount": str(price.total_amount),
            "performers_count": len(performers),
        },
    )
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := OrderDraftSummaryScreen(
                OrderSummaryView(
                    service_name=price.service_name,
                    duration_minutes=price.duration_minutes,
                    objects_count=price.objects_count,
                    service_amount=price.service_amount,
                    platform_fee_amount=price.platform_fee_amount,
                    total_amount=price.total_amount,
                    performers_count=len(performers),
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
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
    order_draft = draft(data)
    await state.update_data(
        return_to_order_after_care_object=True,
        draft={"object_type": str(order_draft["care_object_type"])},
        order_draft=order_draft,
    )
    await state.set_state(CareObjectManagement.name)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := CareObjectNameStepScreen(
                ObjectNameView(
                    object_type_label=CARE_OBJECT_TYPE_LABELS.get(
                        str(order_draft["care_object_type"]),
                        "Объект ухода",
                    )
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
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
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    await state.update_data(
        return_to_order_after_address=True,
        city_ids=[str(city.id) for city in cities],
        city_names=[city.name for city in cities],
        address_draft={},
    )
    await state.set_state(AddressManagement.city)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := AddressCityStepScreen(cities).build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )

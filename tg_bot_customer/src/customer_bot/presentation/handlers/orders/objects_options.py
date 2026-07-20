import logging

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    OrderObjectCallback,
    OrderObjectsDoneCallback,
    OrderOptionsDoneCallback,
    OrderOptionToggleCallback,
    OrderServiceCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.orders.creation_navigation import (
    start_calendar_keyboard,
)
from customer_bot.presentation.handlers.orders.state import (
    OrderCreation,
    care_object_state,
    draft,
    item_by_id,
    selected_ids,
    string_list,
)
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.screens import (
    OrderNoObjectsScreen,
    OrderObjectsStepScreen,
    OrderOptionsStepScreen,
    OrderStartStepScreen,
    RetryLaterScreen,
)
from customer_bot.presentation.view_models import (
    ObjectsStepView,
    ObjectTypeView,
    OptionsStepView,
    SelectableObjectView,
    SelectableOptionView,
)

router = Router(name="orders_objects_options")
logger = logging.getLogger(__name__)


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


__all__ = ["router"]

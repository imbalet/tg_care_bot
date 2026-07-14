from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from customer_bot.application.dto import (
    CareObjectDTO,
    ServiceCategoryDTO,
    SuitablePerformerDTO,
)
from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import ActiveCategoryStore, BackendPort
from customer_bot.presentation.callbacks import (
    OrderAddressCallback,
    OrderCommentSkipCallback,
    OrderCreateCallback,
    OrderObjectCallback,
    OrderPhotoConsentCallback,
    OrderPublishDirectCallback,
    OrderPublishPoolCallback,
    OrderServiceCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.responses import send_step
from customer_bot.presentation.navigation import active_category
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.types import YesNoValue
from customer_bot.presentation.ui import (
    invalid_datetime_text,
    invalid_duration_text,
    order_address_step_text,
    order_addresses_keyboard,
    order_comment_skip_keyboard,
    order_comment_step_text,
    order_draft_summary_text,
    order_duration_step_text,
    order_no_addresses_text,
    order_no_objects_text,
    order_no_services_text,
    order_objects_keyboard,
    order_objects_step_text,
    order_photo_consent_keyboard,
    order_photo_consent_step_text,
    order_publish_keyboard,
    order_published_text,
    order_services_keyboard,
    order_services_step_text,
    order_start_step_text,
    retry_later_text,
    use_buttons_text,
)

router = Router(name="orders")

LOCAL_TZ = ZoneInfo("Europe/Moscow")
MAX_DURATION_HOURS = 24


class OrderCreation(StatesGroup):
    service = State()
    object = State()
    start = State()
    duration = State()
    address = State()
    photo_consent = State()
    comment = State()
    publish = State()


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
    except BackendClientError:
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    if category is None:
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
        return
    draft = _draft(await state.get_data())
    draft.update(
        {
            "service_id": service["id"],
            "service_name": service["name"],
            "care_object_type": service["care_object_type"],
            "location_policy": service["location_policy"],
            "photo_policy": service["photo_policy"],
        },
    )
    try:
        objects = await backend_client.list_care_objects(
            telegram_id=telegram_user_context.telegram_id,
            object_type=str(service["care_object_type"]),
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
    if not objects:
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=order_no_objects_text(str(service["care_object_type"])),
        )
        return
    await state.set_state(OrderCreation.object)
    await state.update_data(
        order_draft=draft,
        order_objects=[_care_object_state(item) for item in objects],
    )
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_objects_step_text(),
        reply_markup=order_objects_keyboard(objects),
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
        return
    data = await state.get_data()
    draft = _draft(data)
    draft["care_object_ids"] = [str(item["id"])]
    draft["objects_count"] = 1
    await state.set_state(OrderCreation.start)
    await state.update_data(order_draft=draft)
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_start_step_text(),
    )


@router.message(OrderCreation.start)
async def enter_start(
    message: Message,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text:
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=invalid_datetime_text(),
        )
        return
    start_at = _parse_local_datetime(message.text)
    if start_at is None:
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=invalid_datetime_text(),
        )
        return
    data = await state.get_data()
    draft = _draft(data)
    draft["start_at"] = start_at.isoformat()
    await state.set_state(OrderCreation.duration)
    await state.update_data(order_draft=draft)
    await send_step(
        bot=bot,
        event=message,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_duration_step_text(),
    )


@router.message(OrderCreation.duration)
async def enter_duration(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    hours = _parse_duration_hours(message.text)
    if hours is None:
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=invalid_duration_text(),
        )
        return
    data = await state.get_data()
    draft = _draft(data)
    start_at = datetime.fromisoformat(str(draft["start_at"]))
    end_at = start_at + timedelta(hours=hours)
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
    except BackendClientError:
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    if not addresses:
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=order_no_addresses_text(),
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
    draft = _draft(data)
    try:
        order = await backend_client.publish_order_pool(
            order_id=UUID(str(draft["order_id"])),
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
    await state.clear()
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_published_text(order),
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
    performer = await _item_by_index(state, "order_performers", callback_data.index)
    if performer is None:
        return
    data = await state.get_data()
    draft = _draft(data)
    try:
        order = await backend_client.publish_order_direct(
            order_id=UUID(str(draft["order_id"])),
            performer_id=UUID(str(performer["performer_id"])),
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
    await state.clear()
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_published_text(order),
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
        consent_value = draft.get("report_photo_consent")
        report_photo_consent = (
            consent_value if isinstance(consent_value, bool) else None
        )
        price = await backend_client.preview_order_price(
            service_id=UUID(str(draft["service_id"])),
            start_at=start_at,
            end_at=end_at,
            objects_count=objects_count,
        )
        order = await backend_client.create_order_draft(
            customer_id=profile.id,
            service_id=UUID(str(draft["service_id"])),
            start_at=start_at,
            end_at=end_at,
            care_object_ids=care_object_ids,
            address_id=address_id,
            customer_comment=str(draft["customer_comment"])
            if draft.get("customer_comment")
            else None,
            report_photo_consent=report_photo_consent,
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
    except BackendValidationError:
        await send_step(
            bot=bot,
            event=event,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=use_buttons_text(),
        )
        return
    except BackendClientError:
        await send_step(
            bot=bot,
            event=event,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    draft["order_id"] = str(order.id)
    await state.set_state(OrderCreation.publish)
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


def _service_states(
    categories: tuple[ServiceCategoryDTO, ...],
) -> list[dict[str, object]]:
    services: list[dict[str, object]] = []
    for category in categories:
        for service in category.services:
            services.append(
                {
                    "id": str(service.id),
                    "name": service.name,
                    "category_code": category.code,
                    "category_name": category.name,
                    "care_object_type": category.care_object_type,
                    "location_policy": service.location_policy,
                    "photo_policy": service.photo_policy,
                },
            )
    return services


def _care_object_state(item: CareObjectDTO) -> dict[str, object]:
    return {"id": str(item.id), "display_name": item.display_name}


def _performer_state(item: SuitablePerformerDTO) -> dict[str, object]:
    return {"performer_id": str(item.performer_id), "full_name": item.full_name}


async def _item_by_index(
    state: FSMContext,
    key: str,
    index: int,
) -> dict[str, object] | None:
    data = await state.get_data()
    items = data.get(key)
    if not isinstance(items, list) or index < 0 or index >= len(items):
        return None
    item = items[index]
    return item if isinstance(item, dict) else None


def _parse_local_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return parsed.replace(tzinfo=LOCAL_TZ)


def _parse_duration_hours(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        hours = int(value.strip())
    except ValueError:
        return None
    if hours < 1 or hours > MAX_DURATION_HOURS:
        return None
    return hours


def _draft(data: dict[str, object]) -> dict[str, object]:
    draft = data.get("order_draft")
    return dict(draft) if isinstance(draft, dict) else {}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]

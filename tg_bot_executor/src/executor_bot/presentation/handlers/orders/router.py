from datetime import datetime
from html import escape
from io import BytesIO
from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from executor_bot.application.dto import AvailableOrderDTO, OrderMatchDTO
from executor_bot.application.errors import BackendClientError, BackendValidationError
from executor_bot.application.ports import (
    ActiveCategoryStore,
    BackendPort,
    ViewedAvailableOrdersStore,
)
from executor_bot.presentation.callbacks import (
    AvailableOrderCardCallback,
    AvailableOrdersOpenCallback,
    DirectAcceptCallback,
    DirectRejectCallback,
    ExecutorDirectResponseCardCallback,
    ExecutorOrderCancelCallback,
    ExecutorOrderCancelConfirmCallback,
    ExecutorOrderCardCallback,
    ExecutorOrderComplaintCallback,
    ExecutorOrderContactCallback,
    ExecutorOrderContactsCallback,
    ExecutorOrderFinishCallback,
    ExecutorOrderLocationCallback,
    ExecutorOrderReportCallback,
    ExecutorOrderReportSkipCallback,
    ExecutorOrderReportSubmitCallback,
    ExecutorOrderReportViewCallback,
    ExecutorOrdersOpenCallback,
    ExecutorOrdersPageCallback,
    ExecutorOrderStartCallback,
    ExecutorOrderSupportCallback,
    ExecutorResponseCardCallback,
    ExecutorResponsesCallback,
    NotificationOrderOpenCallback,
    PoolRespondCallback,
)
from executor_bot.presentation.contexts import TelegramUserContext
from executor_bot.presentation.navigation import active_category
from executor_bot.presentation.services import TelegramResponder
from executor_bot.presentation.ui import (
    available_order_card_keyboard,
    available_orders_keyboard,
    available_orders_setup_text,
    available_orders_text,
    cancel_confirmation_keyboard,
    cancel_confirmation_text,
    direct_accept_created_text,
    direct_conflict_text,
    direct_rejected_text,
    direct_response_card_keyboard,
    fallback_keyboard,
    finish_window_unavailable_text,
    my_order_card_keyboard_for_status,
    my_order_card_text,
    my_orders_page_keyboard,
    my_orders_page_text,
    order_location_keyboard,
    orders_filter_keyboard,
    pool_response_created_text,
    report_attachment_keyboard,
    report_skip_keyboard,
    response_card_keyboard,
    response_card_text,
    responses_keyboard,
    stale_action_keyboard,
    stale_action_text,
    start_window_unavailable_text,
)
from executor_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory

router = Router(name="orders")


class OrderActionForm(StatesGroup):
    report_work = State()
    report_comment = State()
    report_problem = State()
    report_problem_description = State()
    report_attachment = State()
    support_text = State()
    complaint_category = State()
    complaint_text = State()


@router.callback_query(AvailableOrdersOpenCallback.filter())
async def available_orders_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    active_category_store: ActiveCategoryStore,
    viewed_available_orders_store: ViewedAvailableOrdersStore,
    callback_data: AvailableOrdersOpenCallback,
) -> None:
    registration_state = await backend_client.get_registration_state(
        telegram_user_context.telegram_id,
    )
    if registration_state.performer is None:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text="Профиль исполнителя не найден.",
            reply_markup=orders_filter_keyboard(is_available_orders=True),
        )
        return
    category = await active_category(
        backend_client=backend_client,
        active_category_store=active_category_store,
        telegram_id=telegram_user_context.telegram_id,
    )
    try:
        orders = await backend_client.list_available_orders(
            performer_id=registration_state.performer.id,
            category_code=(
                category.code
                if callback_data.scope.value == "current_category"
                and category is not None
                else None
            ),
        )
    except BackendValidationError as error:
        error_text = str(error).lower()
        reason = (
            "unavailable"
            if "unavailable" in error_text
            else "schedule"
            if "schedule" in error_text
            else "address"
            if "address" in error_text or "адрес" in error_text
            else "service"
            if "service" in error_text
            else "accepting"
            if "accepting" in error_text
            else None
        )
        if reason is None:
            raise
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=available_orders_setup_text(reason),
            reply_markup=orders_filter_keyboard(is_available_orders=True),
        )
        return
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text="Не удалось загрузить заказы. Попробуйте позже.",
            reply_markup=orders_filter_keyboard(is_available_orders=True),
        )
        return
    viewed = await viewed_available_orders_store.list_viewed(
        telegram_user_context.telegram_id,
    )
    visible_orders = (
        orders
        if callback_data.show_viewed
        else tuple(order for order in orders if str(order.id) not in viewed)
    )
    await state.update_data(
        available_orders=[
            {
                "id": str(order.id),
                "service_name": order.service_name,
                "start_at": order.start_at.isoformat(),
                "end_at": order.end_at.isoformat(),
                "objects_count": order.objects_count,
                "total_amount": str(order.total_amount),
            }
            for order in visible_orders
        ],
    )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=available_orders_text(visible_orders, callback_data.scope),
        reply_markup=available_orders_keyboard(
            visible_orders,
            scope=callback_data.scope,
            show_viewed=callback_data.show_viewed,
        ),
    )


@router.callback_query(AvailableOrderCardCallback.filter())
async def available_order_card_callback(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    viewed_available_orders_store: ViewedAvailableOrdersStore,
    callback_data: AvailableOrderCardCallback,
) -> None:
    data = await state.get_data()
    items = data.get("available_orders")
    item = (
        next(
            (
                item
                for item in items
                if isinstance(item, dict)
                and str(item.get("id")) == callback_data.order_id
            ),
            None,
        )
        if isinstance(items, list)
        else None
    )
    if item is None:
        await telegram_responder.acknowledge(callback, "Заказ уже недоступен.")
        return
    await viewed_available_orders_store.mark_viewed(
        telegram_user_context.telegram_id,
        callback_data.order_id,
    )
    text = _available_order_card_text(item)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=available_order_card_keyboard(callback_data.order_id),
    )


@router.callback_query(ExecutorOrdersOpenCallback.filter())
async def executor_orders_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await _show_orders_page(
        bot=bot,
        event=callback,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        group="active",
        page=1,
    )


@router.callback_query(ExecutorResponsesCallback.filter())
async def executor_responses_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorResponsesCallback,
) -> None:
    matches: tuple[OrderMatchDTO, ...] = ()
    try:
        matches = await backend_client.list_performer_responses(
            performer_id=await _performer_id(
                backend_client, telegram_user_context.telegram_id
            ),
            group=callback_data.group,
        )
        group_label = {
            "active": "активные",
            "selected": "выбраны, ожидают оплаты",
            "closed": "закрытые",
            "direct": "ожидающие Direct",
        }.get(callback_data.group, callback_data.group)
        lines = ["<b>Мои отклики</b>", "", f"Раздел: {group_label}"]
        for match in matches:
            lines.extend(
                (
                    "",
                    f"<b>Заказ #{escape(str(match.order_id)[:8])}</b>",
                    f"Период: {_match_period(match)}",
                    f"Ответить до: {_match_datetime(match.response_expires_at)}",
                    f"Статус: {_match_status_label(match.status)}",
                    *(
                        (f"Причина закрытия: {escape(match.close_reason)}",)
                        if match.close_reason
                        else ()
                    ),
                ),
            )
        if not matches:
            lines.append("Откликов в этом разделе нет.")
        text = "\n".join(lines)
    except BackendClientError, ValueError:
        text = stale_action_text()
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=responses_keyboard(matches, callback_data.group),
    )


@router.callback_query(ExecutorResponseCardCallback.filter())
async def executor_response_card_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorResponseCardCallback,
) -> None:
    try:
        matches = await backend_client.list_performer_responses(
            performer_id=await _performer_id(
                backend_client,
                telegram_user_context.telegram_id,
            ),
            group=callback_data.group,
        )
        match = next(
            (item for item in matches if str(item.id) == callback_data.match_id),
            None,
        )
        if match is None:
            raise ValueError("Response is unavailable")
        text = response_card_text(match)
        reply_markup = response_card_keyboard(callback_data.group)
    except BackendClientError, ValueError:
        text = stale_action_text()
        reply_markup = stale_action_keyboard()
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=reply_markup,
    )


@router.callback_query(ExecutorDirectResponseCardCallback.filter())
async def executor_direct_response_card_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorDirectResponseCardCallback,
) -> None:
    try:
        matches = await backend_client.list_performer_responses(
            performer_id=await _performer_id(
                backend_client,
                telegram_user_context.telegram_id,
            ),
            group="direct",
        )
        match = next(
            (item for item in matches if str(item.id) == callback_data.match_id),
            None,
        )
        if match is None:
            raise ValueError("Direct invitation is unavailable")
        text = "\n".join(
            (
                "<b>Direct-приглашение</b>",
                "",
                f"Заказ: #{escape(str(match.order_id)[:8])}",
                *(
                    (f"Услуга: {escape(match.service_name)}",)
                    if match.service_name is not None
                    else ()
                ),
                f"Период: {_match_period(match)}",
                *(
                    (f"Сумма: {match.total_amount} ₽",)
                    if match.total_amount is not None
                    else ()
                ),
                *(
                    (f"Расстояние: {match.distance_km} км",)
                    if match.distance_km is not None
                    else ("Расстояние: нет координат",)
                ),
                *(
                    (f"Комментарий заказчика: {escape(match.customer_comment)}",)
                    if match.customer_comment
                    else ()
                ),
                f"Ответить до: {_match_datetime(match.response_expires_at)}",
                f"Статус: {_match_status_label(match.status)}",
            ),
        )
        reply_markup = direct_response_card_keyboard(str(match.id))
    except BackendClientError, ValueError:
        text = stale_action_text()
        reply_markup = stale_action_keyboard()
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=reply_markup,
    )


def _match_datetime(value: object) -> str:
    if hasattr(value, "strftime"):
        return escape(value.strftime("%d.%m.%Y %H:%M"))
    return escape(str(value))


def _match_period(match: object) -> str:
    starts_at = getattr(match, "starts_at", "")
    ends_at = getattr(match, "ends_at", "")
    return f"{_match_datetime(starts_at)} — {_match_datetime(ends_at)}"


@router.callback_query(ExecutorOrdersPageCallback.filter())
async def executor_orders_page_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorOrdersPageCallback,
) -> None:
    await _show_orders_page(
        bot=bot,
        event=callback,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        group=callback_data.group,
        page=callback_data.page,
    )


@router.callback_query(ExecutorOrderCardCallback.filter())
async def executor_order_card_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorOrderCardCallback,
) -> None:
    await _show_executor_order_card(
        callback=callback,
        bot=bot,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        order_id=callback_data.order_id,
        group=callback_data.group,
        page=callback_data.page,
    )


@router.callback_query(NotificationOrderOpenCallback.filter())
async def notification_order_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    viewed_available_orders_store: ViewedAvailableOrdersStore,
    callback_data: NotificationOrderOpenCallback,
) -> None:
    try:
        performer_id = await _performer_id(
            backend_client,
            telegram_user_context.telegram_id,
        )
        orders = await backend_client.list_available_orders(
            performer_id=performer_id,
        )
        order = next(
            (item for item in orders if str(item.id) == callback_data.order_id),
            None,
        )
        if order is not None:
            await viewed_available_orders_store.mark_viewed(
                telegram_user_context.telegram_id,
                callback_data.order_id,
            )
    except BackendClientError, ValueError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=stale_action_text(),
            reply_markup=stale_action_keyboard(),
        )
        return
    if order is None:
        await _show_executor_order_card(
            callback=callback,
            bot=bot,
            backend_client=backend_client,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            order_id=callback_data.order_id,
            group="active",
            page=1,
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=_available_order_card_text(order),
        reply_markup=available_order_card_keyboard(callback_data.order_id),
    )


def _available_order_card_text(order: AvailableOrderDTO | dict[str, object]) -> str:
    if isinstance(order, dict):
        order_id = order.get("id")
        service_name = order.get("service_name")
        start_at = order.get("start_at")
        end_at = order.get("end_at")
        price_type = order.get("price_type")
        objects_count = order.get("objects_count")
        total_amount = order.get("total_amount")
        distance = order.get("distance_km")
    else:
        order_id = order.id
        service_name = order.service_name
        start_at = order.start_at
        end_at = order.end_at
        price_type = order.price_type
        objects_count = order.objects_count
        total_amount = order.total_amount
        distance = order.distance_km
    duration_label = _available_order_duration_label(start_at, end_at, price_type)
    return "\n".join(
        (
            "📦 <b>Доступный заказ</b>",
            "",
            f"ID: #{escape(str(order_id)[:8])}",
            f"Услуга: {escape(str(service_name))}",
            f"🗓 Период: {escape(str(start_at))} — {escape(str(end_at))}",
            *((duration_label,) if duration_label else ()),
            f"Объектов: {escape(str(objects_count))}",
            f"Сумма: {escape(str(total_amount))} ₽",
            (
                f"Расстояние: {escape(str(distance))} км"
                if distance is not None
                else "Расстояние: недоступно (нет координат)"
            ),
        ),
    )


def _available_order_duration_label(
    start_at: object,
    end_at: object,
    price_type: object,
) -> str:
    if price_type != "started_24h":
        return ""
    try:
        start = (
            start_at
            if isinstance(start_at, datetime)
            else datetime.fromisoformat(str(start_at))
        )
        end = (
            end_at
            if isinstance(end_at, datetime)
            else datetime.fromisoformat(str(end_at))
        )
    except ValueError:
        return ""
    minutes = max(0, int((end - start).total_seconds() // 60))
    units = max(1, (minutes + 1439) // 1440)
    duration = (
        f"{units} сутки" if units % 10 == 1 and units % 100 != 11 else f"{units} суток"
    )
    return f"⏱ Длительность: {duration}"


async def _performer_id(backend_client: BackendPort, telegram_id: int) -> UUID:
    state = await backend_client.get_registration_state(telegram_id)
    if state.performer is None:
        raise ValueError("Performer is not registered")
    return state.performer.id


@router.callback_query(ExecutorOrderLocationCallback.filter())
async def order_location_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorOrderLocationCallback,
) -> None:
    try:
        performer_id = await _performer_id(
            backend_client, telegram_user_context.telegram_id
        )
        location = await backend_client.get_performer_order_location(
            performer_id=performer_id, order_id=UUID(callback_data.order_id)
        )
        lines = ["<b>Место оказания</b>", "", location.city_name]
        if location.district_name:
            lines.append(location.district_name)
        if location.address_text:
            lines.append(location.address_text)
        for label, value in (
            ("Подъезд", location.entrance),
            ("Этаж", location.floor),
            ("Квартира", location.apartment),
            ("Комментарий", location.comment),
        ):
            if value:
                lines.append(f"{label}: {value}")
        text = "\n".join(lines)
    except BackendClientError, ValueError:
        text = stale_action_text()
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=(
            stale_action_keyboard()
            if text == stale_action_text()
            else order_location_keyboard(
                order_id=callback_data.order_id,
                group=callback_data.group,
                page=callback_data.page,
            )
        ),
    )


async def _refresh_order_card(
    *,
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    context: TelegramUserContext,
    order_id: UUID,
    group: str = "active",
    page: int = 1,
) -> None:
    performer_id = await _performer_id(backend_client, context.telegram_id)
    order = await backend_client.get_performer_order_card(
        performer_id=performer_id, order_id=order_id
    )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=context.telegram_id,
        text=my_order_card_text(order),
        reply_markup=my_order_card_keyboard_for_status(
            status=order.status,
            order_id=str(order.id),
            group=group,
            page=page,
            start_at=order.start_at,
            end_at=order.end_at,
        ),
    )


@router.callback_query(ExecutorOrderStartCallback.filter())
async def order_start_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorOrderStartCallback,
) -> None:
    try:
        await backend_client.start_order(
            performer_id=await _performer_id(
                backend_client, telegram_user_context.telegram_id
            ),
            order_id=UUID(callback_data.order_id),
        )
        await _refresh_order_card(
            callback=callback,
            bot=bot,
            backend_client=backend_client,
            telegram_responder=telegram_responder,
            context=telegram_user_context,
            order_id=UUID(callback_data.order_id),
        )
    except (BackendClientError, ValueError) as exc:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(
                start_window_unavailable_text()
                if "start window" in str(exc).lower()
                else stale_action_text()
            ),
            reply_markup=stale_action_keyboard(),
        )


@router.callback_query(ExecutorOrderFinishCallback.filter())
async def order_finish_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorOrderFinishCallback,
) -> None:
    try:
        await backend_client.finish_order(
            performer_id=await _performer_id(
                backend_client, telegram_user_context.telegram_id
            ),
            order_id=UUID(callback_data.order_id),
        )
        await _refresh_order_card(
            callback=callback,
            bot=bot,
            backend_client=backend_client,
            telegram_responder=telegram_responder,
            context=telegram_user_context,
            order_id=UUID(callback_data.order_id),
        )
    except (BackendClientError, ValueError) as exc:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(
                finish_window_unavailable_text()
                if "finish window" in str(exc).lower()
                else stale_action_text()
            ),
            reply_markup=stale_action_keyboard(),
        )


@router.callback_query(ExecutorOrderContactCallback.filter())
async def order_contact_callback(
    callback: CallbackQuery,
    bot: Bot,
    telegram_responder: TelegramResponder,
    backend_client: BackendPort,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorOrderContactCallback,
) -> None:
    try:
        result = await backend_client.create_contact_request(
            telegram_id=telegram_user_context.telegram_id,
            order_id=UUID(callback_data.order_id),
        )
        await telegram_responder.acknowledge(
            callback,
            "Запрос отправлен заказчику"
            if result.status == "sent"
            else "Связь недоступна",
            show_alert=True,
        )
    except BackendClientError:
        await telegram_responder.acknowledge(
            callback, "Запрос контакта сейчас недоступен", show_alert=True
        )


@router.callback_query(ExecutorOrderContactsCallback.filter())
async def order_contacts_callback(
    callback: CallbackQuery,
    bot: Bot,
    telegram_responder: TelegramResponder,
    backend_client: BackendPort,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorOrderContactsCallback,
) -> None:
    try:
        result = await backend_client.get_order_contacts(
            telegram_id=telegram_user_context.telegram_id,
            order_id=UUID(callback_data.order_id),
        )
        await telegram_responder.acknowledge(callback, "Контакты доступны")
        if result.contact_phone and result.contact_name:
            await telegram_responder.send_contact(
                bot=bot,
                event=callback,
                phone_number=result.contact_phone,
                first_name=result.contact_name,
            )
        if result.contact_telegram_username:
            username = result.contact_telegram_username.lstrip("@")
            await telegram_responder.send_notice(
                bot=bot,
                event=callback,
                telegram_id=telegram_user_context.telegram_id,
                text=f"Telegram заказчика: @{username}",
                reply_markup=(
                    InlineKeyboardFactory()
                    .url_button("Открыть Telegram", f"https://t.me/{username}")
                    .as_markup()
                ),
            )
    except BackendClientError:
        await telegram_responder.acknowledge(
            callback, "Контакты сейчас недоступны", show_alert=True
        )


@router.callback_query(ExecutorOrderSupportCallback.filter())
async def order_support_callback(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorOrderSupportCallback,
) -> None:
    await state.clear()
    await state.set_state(OrderActionForm.support_text)
    await state.update_data(order_id=callback_data.order_id)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text="<b>Поддержка по заказу</b>\n\nОпишите вопрос.",
        reply_markup=None,
        create_new=True,
    )


@router.message(OrderActionForm.support_text)
async def order_support_text(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Опишите вопрос текстом.",
            create_new=True,
        )
        return
    data = await state.get_data()
    try:
        await backend_client.create_support_request(
            telegram_id=telegram_user_context.telegram_id,
            order_id=UUID(str(data["order_id"])),
            request_type="order",
            text=message.text.strip(),
        )
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Обращение отправлено в поддержку.",
            reply_markup=fallback_keyboard(),
            create_new=True,
        )
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Не удалось отправить обращение. Попробуйте позже.",
            reply_markup=fallback_keyboard(),
            create_new=True,
        )
    finally:
        await state.clear()


@router.callback_query(ExecutorOrderComplaintCallback.filter())
async def order_complaint_callback(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorOrderComplaintCallback,
) -> None:
    await state.clear()
    await state.set_state(OrderActionForm.complaint_category)
    await state.update_data(order_id=callback_data.order_id)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text="<b>Жалоба</b>\n\nУкажите категорию жалобы.",
        reply_markup=None,
        create_new=True,
    )


@router.message(OrderActionForm.complaint_category)
async def complaint_category(
    message: Message,
    state: FSMContext,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Укажите категорию жалобы.",
            create_new=True,
        )
        return
    await state.update_data(category=message.text.strip())
    await state.set_state(OrderActionForm.complaint_text)
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text="Опишите жалобу.",
        create_new=True,
    )


@router.message(OrderActionForm.complaint_text)
async def complaint_text(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Опишите жалобу текстом.",
            create_new=True,
        )
        return
    data = await state.get_data()
    try:
        await backend_client.create_complaint(
            telegram_id=telegram_user_context.telegram_id,
            order_id=UUID(str(data["order_id"])),
            category="order_problem",
            text=message.text.strip(),
        )
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Жалоба отправлена.",
            reply_markup=fallback_keyboard(),
            create_new=True,
        )
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Не удалось отправить жалобу. Попробуйте позже.",
            reply_markup=fallback_keyboard(),
            create_new=True,
        )
    finally:
        await state.clear()


@router.callback_query(ExecutorOrderCancelCallback.filter())
async def order_cancel_preview_callback(
    callback: CallbackQuery,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorOrderCancelCallback,
) -> None:
    await telegram_responder.acknowledge(callback)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=cancel_confirmation_text(),
        reply_markup=cancel_confirmation_keyboard(callback_data.order_id),
        create_new=False,
    )


@router.callback_query(ExecutorOrderCancelConfirmCallback.filter())
async def order_cancel_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorOrderCancelConfirmCallback,
) -> None:
    try:
        await backend_client.cancel_order(
            performer_id=await _performer_id(
                backend_client, telegram_user_context.telegram_id
            ),
            order_id=UUID(callback_data.order_id),
        )
        await telegram_responder.acknowledge(callback, "Заказ отменён")
    except BackendClientError, ValueError:
        await telegram_responder.acknowledge(
            callback, "Отмена недоступна", show_alert=True
        )


@router.callback_query(ExecutorOrderReportCallback.filter())
async def order_report_callback(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorOrderReportCallback,
) -> None:
    await state.clear()
    await state.set_state(OrderActionForm.report_work)
    await state.update_data(order_id=callback_data.order_id)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text="<b>Отчёт</b>\n\nОпишите выполненную работу.",
        reply_markup=None,
        create_new=True,
    )


@router.callback_query(ExecutorOrderReportViewCallback.filter())
async def order_report_view_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorOrderReportViewCallback,
) -> None:
    try:
        report = await backend_client.get_performer_order_report(
            performer_id=await _performer_id(
                backend_client, telegram_user_context.telegram_id
            ),
            order_id=UUID(callback_data.order_id),
        )
        lines = [
            "<b>Отчёт по заказу</b>",
            "",
            f"Выполнено: {report.completed_work}",
        ]
        if report.comment:
            lines.extend(("", f"Комментарий: {report.comment}"))
        if report.problem_flag and report.problem_description:
            lines.extend(("", f"Проблема: {report.problem_description}"))
        for file in report.files:
            lines.extend(("", f"Файл: {file.signed_url}"))
        text = "\n".join(lines)
    except BackendClientError, ValueError:
        text = stale_action_text()
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=stale_action_keyboard() if text == stale_action_text() else None,
        create_new=True,
    )


@router.message(OrderActionForm.report_work)
async def report_work(
    message: Message,
    state: FSMContext,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Введите описание выполненной работы текстом.",
            create_new=True,
        )
        return
    await state.update_data(completed_work=message.text.strip())
    await state.set_state(OrderActionForm.report_comment)
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text="Добавьте комментарий или пропустите этот шаг.",
        reply_markup=report_skip_keyboard("comment"),
        create_new=True,
    )


@router.message(OrderActionForm.report_comment)
async def report_comment(
    message: Message,
    state: FSMContext,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.update_data(comment=message.text)
    await state.set_state(OrderActionForm.report_problem)
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text="Была проблема? Ответьте да или нет.",
        create_new=True,
    )


@router.message(OrderActionForm.report_problem)
async def report_problem(
    message: Message,
    state: FSMContext,
    backend_client: BackendPort,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or message.text.lower() not in {"да", "нет", "yes", "no"}:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Ответьте «да» или «нет».",
            create_new=True,
        )
        return
    problem = message.text.lower() in {"да", "yes"}
    await state.update_data(problem_flag=problem, problem_description=None)
    if problem:
        await state.set_state(OrderActionForm.report_problem_description)
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Опишите проблему или пропустите описание.",
            reply_markup=report_skip_keyboard("problem_description"),
            create_new=True,
        )
        return
    await state.set_state(OrderActionForm.report_attachment)
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text="Прикрепите фото или документ либо пропустите этот шаг.",
        reply_markup=report_attachment_keyboard(has_attachments=False),
        create_new=True,
    )


@router.message(OrderActionForm.report_problem_description)
async def report_problem_description(
    message: Message,
    state: FSMContext,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Опишите проблему текстом.",
            create_new=True,
        )
        return
    await state.update_data(problem_description=message.text.strip())
    await state.set_state(OrderActionForm.report_attachment)
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text="Прикрепите фото или документ либо пропустите этот шаг.",
        reply_markup=report_attachment_keyboard(has_attachments=False),
        create_new=True,
    )


@router.message(OrderActionForm.report_attachment, F.photo | F.document)
async def report_attachment(
    message: Message,
    state: FSMContext,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    attachment = message.photo[-1] if message.photo else message.document
    if attachment is None:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Прикрепите фото или документ либо нажмите «Пропустить».",
            create_new=True,
        )
        return
    telegram_file = await bot.get_file(attachment.file_id)
    if telegram_file.file_path is None:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Файл недоступен. Попробуйте ещё раз.",
            create_new=True,
        )
        return
    buffer = BytesIO()
    await bot.download_file(telegram_file.file_path, destination=buffer)
    content_type = "image/jpeg"
    filename = "report-photo.jpg"
    if message.document is not None:
        content_type = message.document.mime_type or "application/octet-stream"
        filename = message.document.file_name or "report-file"
    try:
        file = await backend_client.upload_file(
            telegram_id=telegram_user_context.telegram_id,
            filename=filename,
            content=buffer.getvalue(),
            content_type=content_type,
        )
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text="Не удалось загрузить файл. Попробуйте ещё раз.",
            create_new=True,
        )
        return
    data = await state.get_data()
    file_ids = [str(item) for item in data.get("file_ids", [])]
    file_ids.append(str(file.id))
    await state.update_data(file_ids=file_ids)
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text="Файл добавлен. Добавьте ещё или нажмите «Готово».",
        reply_markup=report_attachment_keyboard(has_attachments=True),
        create_new=True,
    )


@router.message(OrderActionForm.report_attachment, F.text)
async def report_attachment_text(
    message: Message,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text="Используйте inline-кнопку «Пропустить» или прикрепите фото/документ.",
        create_new=True,
    )


async def _submit_order_report(
    event: Message | CallbackQuery,
    state: FSMContext,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    try:
        await backend_client.submit_order_report(
            performer_id=await _performer_id(
                backend_client, telegram_user_context.telegram_id
            ),
            order_id=UUID(str(data["order_id"])),
            completed_work=str(data["completed_work"]),
            comment=data.get("comment")
            if isinstance(data.get("comment"), str)
            else None,
            problem_flag=bool(data.get("problem_flag")),
            problem_description=(
                data.get("problem_description")
                if isinstance(data.get("problem_description"), str)
                else None
            ),
            file_ids=tuple(UUID(str(item)) for item in data.get("file_ids", [])),
        )
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text="Отчёт отправлен заказчику.",
            reply_markup=fallback_keyboard(),
            create_new=True,
        )
    except BackendClientError, ValueError:
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text="Не удалось отправить отчёт. Попробуйте ещё раз.",
            reply_markup=fallback_keyboard(),
            create_new=True,
        )
    finally:
        await state.clear()


@router.callback_query(ExecutorOrderReportSkipCallback.filter())
async def report_skip_callback(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: ExecutorOrderReportSkipCallback,
) -> None:
    await telegram_responder.acknowledge(callback)
    if callback_data.step == "comment":
        await state.update_data(comment=None)
        await state.set_state(OrderActionForm.report_problem)
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text="Была проблема? Ответьте да или нет.",
            create_new=True,
        )
        return
    if callback_data.step == "attachment":
        await _submit_order_report(
            callback,
            state,
            bot,
            backend_client,
            telegram_responder,
            telegram_user_context,
        )
        return
    if callback_data.step == "problem_description":
        await state.update_data(problem_description=None)
        await state.set_state(OrderActionForm.report_attachment)
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text="Прикрепите фото или документ либо пропустите этот шаг.",
            reply_markup=report_attachment_keyboard(has_attachments=False),
            create_new=True,
        )
        return
    await telegram_responder.acknowledge(
        callback, "Шаг уже недоступен", show_alert=True
    )


@router.callback_query(ExecutorOrderReportSubmitCallback.filter())
async def report_submit_callback(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await telegram_responder.acknowledge(callback)
    await _submit_order_report(
        callback,
        state,
        bot,
        backend_client,
        telegram_responder,
        telegram_user_context,
    )


async def _show_executor_order_card(
    *,
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    order_id: str,
    group: str,
    page: int,
) -> None:
    try:
        state = await backend_client.get_registration_state(
            telegram_user_context.telegram_id,
        )
        if state.performer is None:
            raise ValueError("Performer is not registered")
        order = await backend_client.get_performer_order_card(
            performer_id=state.performer.id,
            order_id=UUID(order_id),
        )
    except BackendClientError, ValueError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=stale_action_text(),
            reply_markup=stale_action_keyboard(),
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=my_order_card_text(
            order,
        ),
        reply_markup=my_order_card_keyboard_for_status(
            status=order.status,
            order_id=str(order.id),
            group=group,
            page=page,
            start_at=order.start_at,
            end_at=order.end_at,
        ),
    )


@router.callback_query(PoolRespondCallback.filter())
async def pool_response_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    viewed_available_orders_store: ViewedAvailableOrdersStore,
    callback_data: PoolRespondCallback,
) -> None:
    try:
        state = await backend_client.get_registration_state(
            telegram_user_context.telegram_id,
        )
        if state.performer is None:
            raise ValueError("Performer is not registered")
        await backend_client.create_pool_response(
            order_id=UUID(callback_data.order_id),
            performer_id=state.performer.id,
        )
        await viewed_available_orders_store.mark_viewed(
            telegram_user_context.telegram_id,
            callback_data.order_id,
        )
        text = pool_response_created_text()
    except BackendClientError, ValueError:
        text = "Отклик уже недоступен. Откройте список заказов заново."
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=orders_filter_keyboard(is_available_orders=True),
    )


@router.callback_query(DirectAcceptCallback.filter())
async def direct_accept_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: DirectAcceptCallback,
) -> None:
    try:
        state = await backend_client.get_registration_state(
            telegram_user_context.telegram_id,
        )
        if state.performer is None:
            raise ValueError("Performer is not registered")
        await backend_client.accept_direct_match(
            match_id=UUID(callback_data.match_id),
            performer_id=state.performer.id,
        )
        text = direct_accept_created_text()
    except BackendClientError as exc:
        text = direct_conflict_text(str(exc))
    except ValueError:
        text = "Direct-приглашение уже недоступно."
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=orders_filter_keyboard(is_available_orders=False),
    )


@router.callback_query(DirectRejectCallback.filter())
async def direct_reject_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: DirectRejectCallback,
) -> None:
    try:
        state = await backend_client.get_registration_state(
            telegram_user_context.telegram_id,
        )
        if state.performer is None:
            raise ValueError("Performer is not registered")
        await backend_client.reject_direct_match(
            match_id=UUID(callback_data.match_id),
            performer_id=state.performer.id,
        )
        text = direct_rejected_text()
    except BackendClientError, ValueError:
        text = "Direct-приглашение уже недоступно."
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=orders_filter_keyboard(is_available_orders=False),
    )


async def _show_orders_page(
    *,
    bot: Bot,
    event: CallbackQuery,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_id: int,
    group: str,
    page: int,
) -> None:
    try:
        state = await backend_client.get_registration_state(telegram_id)
        if state.performer is None:
            raise ValueError("Performer is not registered")
        orders = await backend_client.list_performer_orders(
            performer_id=state.performer.id,
            group=group,
            page=page,
        )
    except BackendClientError, ValueError:
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_id,
            text=stale_action_text(),
            reply_markup=stale_action_keyboard(),
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_id,
        text=my_orders_page_text(orders, group),
        reply_markup=my_orders_page_keyboard(orders, group),
    )


def _match_status_label(status: str) -> str:
    return {
        "pending": "ожидает ответа",
        "active": "активен",
        "selected": "выбран",
        "confirmed": "подтверждён",
        "rejected": "отклонён",
        "expired": "истёк",
        "cancelled": "отменён",
    }.get(status, escape(status))


__all__ = ["router"]

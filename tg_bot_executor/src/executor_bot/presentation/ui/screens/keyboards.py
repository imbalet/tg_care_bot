from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Protocol

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from executor_bot.application.dto import CalendarOverrideDTO
from executor_bot.presentation.callbacks import (
    AcceptingOrdersCallback,
    AvailableOrderCardCallback,
    AvailableOrdersOpenCallback,
    AvatarDeleteCallback,
    AvatarOpenCallback,
    AvatarUploadCallback,
    CalendarCancelUnavailableCallback,
    CalendarCustomScheduleCallback,
    CalendarOpenCallback,
    CalendarScheduleCallback,
    CalendarUnavailableCallback,
    CategoryChangeCallback,
    CategorySelectCallback,
    DirectAcceptCallback,
    DirectRejectCallback,
    ExecutorDirectResponseCardCallback,
    ExecutorOrderCancelCallback,
    ExecutorOrderCancelConfirmCallback,
    ExecutorOrderCardCallback,
    ExecutorOrderComplaintCallback,
    ExecutorOrderContactCallback,
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
    HelpCallback,
    MainMenuCallback,
    NearbyOrderNotificationsCallback,
    PoolRespondCallback,
    ProfileOpenCallback,
    RegistrationCityCallback,
    RegistrationConfirmCallback,
    RegistrationContactCallback,
    RegistrationEditCallback,
    RegistrationLegalAcceptCallback,
    ServiceLimitCallback,
    ServicesOpenCallback,
    ServiceToggleCallback,
    SupportOpenCallback,
    WorkAddressAddCallback,
    WorkAddressCityCallback,
    WorkAddressCurrentCallback,
    WorkAddressDeleteCallback,
    WorkAddressesOpenCallback,
    WorkAddressRetryCallback,
    WorkAddressSelectCallback,
    WorkAddressSkipCallback,
    WorkAddressSuggestionCallback,
)
from executor_bot.presentation.types import ContactMethod, OrderFilterScope
from executor_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from executor_bot.presentation.ui.screens.labels import MsgKey


class CityButtonView(Protocol):
    @property
    def name(self) -> str:
        pass


CATEGORY_EMOJIS = {
    "child": "👶",
    "ward": "🧓",
    "pet": "🐾",
}


def legal_acceptance_keyboard(documents: Sequence[object] = ()) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    for index, document in enumerate(documents, start=1):
        url = str(getattr(document, "content_url", ""))
        if url.startswith("https://"):
            keyboard.url_button(f"Документ {index}", url)
    return (
        keyboard.button("Принять и продолжить", RegistrationLegalAcceptCallback())
        .button(MsgKey.HELP, HelpCallback())
        .as_markup()
    )


def select_city_keyboard(cities: Sequence[CityButtonView]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    for index, city in enumerate(cities):
        keyboard.button(city.name, RegistrationCityCallback(index=index))
    return keyboard.as_markup()


def contact_methods_keyboard() -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button("Telegram", RegistrationContactCallback(method=ContactMethod.TELEGRAM))
        .button("Телефон", RegistrationContactCallback(method=ContactMethod.PHONE))
        .button(
            "Telegram и телефон",
            RegistrationContactCallback(method=ContactMethod.BOTH),
        )
        .as_markup()
    )


def phone_contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Поделиться номером", request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Нажмите кнопку ниже",
    )


def registration_summary_keyboard() -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button(MsgKey.CONFIRM, RegistrationConfirmCallback())
        .button(MsgKey.EDIT, RegistrationEditCallback())
        .as_markup()
    )


def category_select_keyboard(categories: Sequence[object]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    for category in categories:
        code = str(getattr(category, "code", ""))
        name = str(getattr(category, "name", code))
        care_object_type = str(getattr(category, "care_object_type", ""))
        emoji = CATEGORY_EMOJIS.get(care_object_type, "")
        keyboard.button(
            f"{emoji} {name}".strip(),
            CategorySelectCallback(code=code),
        )
    return keyboard.as_markup()


def main_menu_keyboard(category: object | None = None) -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button(MsgKey.AVAILABLE_ORDERS, AvailableOrdersOpenCallback())
        .button(MsgKey.MY_ORDERS, ExecutorOrdersOpenCallback())
        .button("Мои отклики", ExecutorResponsesCallback())
        .button(MsgKey.SERVICES, ServicesOpenCallback())
        .button(MsgKey.CALENDAR, CalendarOpenCallback())
        .button(MsgKey.WORK_ADDRESS, WorkAddressesOpenCallback())
        .button(MsgKey.AVATAR, AvatarOpenCallback())
        .button(MsgKey.PROFILE, ProfileOpenCallback())
        .button(MsgKey.HELP, HelpCallback())
        .button(MsgKey.SWITCH_CATEGORY, CategoryChangeCallback())
        .as_markup()
    )


def fallback_keyboard(
    *,
    include_main_menu: bool = True,
    include_help: bool = True,
    include_support: bool = True,
    support_label: str = "Поддержка",
    support_url: str | None = None,
    legal_documents: tuple[object, ...] = (),
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    if include_main_menu:
        keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback())
    for index, document in enumerate(legal_documents, start=1):
        url = str(getattr(document, "content_url", ""))
        if url.startswith(("https://", "http://")):
            keyboard.url_button(f"Документ {index}", url)
    if isinstance(support_url, str) and _valid_telegram_url(support_url):
        keyboard.url_button(support_label, support_url)
    if include_help:
        keyboard.button(MsgKey.HELP, HelpCallback())
    if include_support:
        keyboard.button("Связаться с поддержкой", SupportOpenCallback())
    return keyboard.as_markup()


def stale_action_keyboard() -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button(MsgKey.MAIN_MENU, MainMenuCallback())
        .button("Поддержка", SupportOpenCallback())
        .as_markup()
    )


def support_keyboard(
    *,
    label: str,
    telegram_url: str | None,
    include_main_menu: bool = True,
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    if isinstance(telegram_url, str) and _valid_telegram_url(telegram_url):
        keyboard.url_button(label, telegram_url)
    if include_main_menu:
        keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback())
    return keyboard.as_markup()


def orders_filter_keyboard(
    *,
    is_available_orders: bool,
    scope: OrderFilterScope = OrderFilterScope.CURRENT_CATEGORY,
    show_viewed: bool = False,
) -> InlineKeyboardMarkup:
    current_callback = (
        AvailableOrdersOpenCallback(
            scope=OrderFilterScope.CURRENT_CATEGORY,
            show_viewed=show_viewed,
        )
        if is_available_orders
        else ExecutorOrdersOpenCallback(scope=OrderFilterScope.CURRENT_CATEGORY)
    )
    all_callback = (
        AvailableOrdersOpenCallback(scope=OrderFilterScope.ALL, show_viewed=show_viewed)
        if is_available_orders
        else ExecutorOrdersOpenCallback(scope=OrderFilterScope.ALL)
    )
    keyboard = InlineKeyboardFactory()
    if scope == OrderFilterScope.ALL:
        keyboard.button("📌 Текущее направление", current_callback)
    else:
        keyboard.button("Все направления", all_callback)
    if is_available_orders:
        keyboard.button(
            "Скрыть просмотренные" if show_viewed else "Показать просмотренные",
            AvailableOrdersOpenCallback(scope=scope, show_viewed=not show_viewed),
        )
    return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()


def responses_keyboard(items: Sequence[object], group: str) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    for item in items:
        order_id = str(getattr(item, "order_id", ""))
        if not order_id:
            continue
        status = str(getattr(item, "status", ""))
        if group == "direct":
            match_id = str(getattr(item, "id", ""))
            if not match_id:
                continue
            keyboard.button(
                f"Direct #{order_id[:8]} · {_response_status_label(status)}",
                ExecutorDirectResponseCardCallback(match_id=match_id),
            )
        else:
            keyboard.button(
                f"Заказ #{order_id[:8]} · {_response_status_label(status)}",
                ExecutorResponseCardCallback(order_id=order_id, group=group),
            )
    keyboard.button("Активные", ExecutorResponsesCallback(group="active"))
    keyboard.button("Выбранные", ExecutorResponsesCallback(group="selected"))
    keyboard.button("Закрытые", ExecutorResponsesCallback(group="closed"))
    keyboard.button("Direct", ExecutorResponsesCallback(group="direct"))
    return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()


def direct_response_card_keyboard(match_id: str) -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button("Принять", DirectAcceptCallback(match_id=match_id))
        .button("Отклонить", DirectRejectCallback(match_id=match_id))
        .button("К direct", ExecutorResponsesCallback(group="direct"))
        .button(MsgKey.MAIN_MENU, MainMenuCallback())
        .as_markup()
    )


def _response_status_label(status: str) -> str:
    return {
        "pending": "ожидает решения",
        "active": "активен",
        "selected": "выбран",
        "confirmed": "подтверждён",
        "rejected": "отклонён",
        "expired": "истёк",
        "cancelled": "отменён",
    }.get(status, status)


def available_orders_keyboard(
    items: Sequence[object],
    *,
    scope: OrderFilterScope = OrderFilterScope.CURRENT_CATEGORY,
    show_viewed: bool = False,
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    for item in items:
        order_id = str(getattr(item, "id", ""))
        service_name = str(getattr(item, "service_name", "Заказ"))
        keyboard.button(
            f"Открыть #{order_id[:8]}: {service_name}",
            AvailableOrderCardCallback(order_id=order_id),
        )
    return (
        keyboard.button(
            "Только текущее направление"
            if scope == OrderFilterScope.ALL
            else "Все направления",
            AvailableOrdersOpenCallback(
                scope=(
                    OrderFilterScope.CURRENT_CATEGORY
                    if scope == OrderFilterScope.ALL
                    else OrderFilterScope.ALL
                ),
                show_viewed=show_viewed,
            ),
        )
        .button(
            "Скрыть просмотренные" if show_viewed else "Показать просмотренные",
            AvailableOrdersOpenCallback(scope=scope, show_viewed=not show_viewed),
        )
        .button(MsgKey.MAIN_MENU, MainMenuCallback())
        .as_markup()
    )


def available_order_card_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button("Откликнуться", PoolRespondCallback(order_id=order_id))
        .button(MsgKey.MAIN_MENU, MainMenuCallback())
        .as_markup()
    )


def cancel_confirmation_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button(
            "Да, отменить заказ",
            ExecutorOrderCancelConfirmCallback(order_id=order_id),
        )
        .button(
            "Нет, вернуться к заказу",
            ExecutorOrderCardCallback(order_id=order_id),
        )
        .as_markup()
    )


def direct_offer_keyboard(match_id: str) -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button("Принять", DirectAcceptCallback(match_id=match_id))
        .button("Отклонить", DirectRejectCallback(match_id=match_id))
        .as_markup()
    )


def my_orders_page_keyboard(page: object, group: str) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    items = getattr(page, "items", ())
    page_number = int(getattr(page, "page", 1))
    total_pages = int(getattr(page, "total_pages", 0))
    for index, item in enumerate(items, start=1):
        order_id = getattr(item, "id", None)
        service_name = str(getattr(item, "service_name", f"Заказ {index}"))
        if order_id is not None:
            keyboard.button(
                f"{index}. {service_name}",
                ExecutorOrderCardCallback(
                    order_id=str(order_id),
                    group=group,
                    page=page_number,
                ),
            )
    if group != "active":
        keyboard.button("Активные", ExecutorOrdersPageCallback(group="active", page=1))
    if group != "archive":
        keyboard.button("Архив", ExecutorOrdersPageCallback(group="archive", page=1))
    if page_number > 1:
        keyboard.button(
            "Назад",
            ExecutorOrdersPageCallback(group=group, page=page_number - 1),
        )
    if total_pages > page_number:
        keyboard.button(
            "Дальше",
            ExecutorOrdersPageCallback(group=group, page=page_number + 1),
        )
    return (
        keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback())
        .button("Поддержка", SupportOpenCallback())
        .as_markup()
    )


def my_order_card_keyboard(*, group: str, page: int) -> InlineKeyboardMarkup:
    return my_order_card_keyboard_for_status(status=None, group=group, page=page)


def report_skip_keyboard(step: str) -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button(
            "Пропустить",
            ExecutorOrderReportSkipCallback(step=step),
        )
        .as_markup()
    )


def report_attachment_keyboard(*, has_attachments: bool) -> InlineKeyboardMarkup:
    if has_attachments:
        return (
            InlineKeyboardFactory()
            .button("Готово", ExecutorOrderReportSubmitCallback())
            .as_markup()
        )
    return report_skip_keyboard("attachment")


def my_order_card_keyboard_for_status(
    *,
    status: str | None,
    order_id: str | None = None,
    group: str,
    page: int,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    if order_id is not None and status in {
        "confirmed",
        "in_progress",
        "waiting_report",
        "report_submitted",
    }:
        keyboard.button(
            "Открыть адрес",
            ExecutorOrderLocationCallback(order_id=order_id, group=group, page=page),
        )
        keyboard.button(
            "Попросить связаться", ExecutorOrderContactCallback(order_id=order_id)
        )
    start_window_open = (
        start_at is None
        or end_at is None
        or (
            datetime.now(UTC) >= start_at - timedelta(minutes=30)
            and datetime.now(UTC) < end_at
        )
    )
    if order_id is not None and status == "confirmed" and start_window_open:
        keyboard.button("Я на месте", ExecutorOrderStartCallback(order_id=order_id))
        keyboard.button(
            "Не могу выполнить", ExecutorOrderCancelCallback(order_id=order_id)
        )
    if order_id is not None and status == "in_progress":
        keyboard.button(
            "Завершить выполнение", ExecutorOrderFinishCallback(order_id=order_id)
        )
    if order_id is not None and status == "waiting_report":
        keyboard.button(
            "Отправить отчёт", ExecutorOrderReportCallback(order_id=order_id)
        )
    if order_id is not None and status in {"report_submitted", "completed"}:
        keyboard.button(
            "Открыть отчёт", ExecutorOrderReportViewCallback(order_id=order_id)
        )
    if order_id is not None and status in {
        "waiting_report",
        "report_submitted",
        "completed",
    }:
        keyboard.button("Поддержка", ExecutorOrderSupportCallback(order_id=order_id))
        keyboard.button(
            "Подать жалобу", ExecutorOrderComplaintCallback(order_id=order_id)
        )
    return (
        keyboard.button("К списку", ExecutorOrdersPageCallback(group=group, page=page))
        .button(MsgKey.MAIN_MENU, MainMenuCallback())
        .button("Поддержка", SupportOpenCallback())
        .as_markup()
    )


def order_location_keyboard(
    *,
    order_id: str,
    group: str,
    page: int,
) -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button(
            "К заказу",
            ExecutorOrderCardCallback(order_id=order_id, group=group, page=page),
        )
        .button(MsgKey.MAIN_MENU, MainMenuCallback())
        .as_markup()
    )


def work_addresses_keyboard(items: Sequence[object]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory().button(
        MsgKey.ADD_ADDRESS,
        WorkAddressAddCallback(),
    )
    for index, _item in enumerate(items):
        keyboard.button(f"№{index + 1}", WorkAddressSelectCallback(index=index))
    return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()


def work_address_created_keyboard() -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button("К рабочим адресам", WorkAddressesOpenCallback())
        .button(MsgKey.MAIN_MENU, MainMenuCallback())
        .as_markup()
    )


def work_address_card_keyboard(index: int) -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button("Сделать текущим", WorkAddressCurrentCallback(index=index))
        .button(MsgKey.DELETE, WorkAddressDeleteCallback(index=index))
        .button(MsgKey.BACK_TO_LIST, WorkAddressesOpenCallback())
        .as_markup()
    )


def work_address_city_keyboard(
    cities: Sequence[CityButtonView],
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    for index, city in enumerate(cities):
        keyboard.button(city.name, WorkAddressCityCallback(index=index))
    return keyboard.as_markup()


def work_address_suggestions_keyboard(
    suggestions: Sequence[object],
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    for index, _suggestion in enumerate(suggestions):
        keyboard.button(
            f"№{index + 1}",
            WorkAddressSuggestionCallback(index=index),
        )
    return keyboard.button("Ввести заново", WorkAddressRetryCallback()).as_markup()


def work_address_skip_keyboard() -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button(MsgKey.SKIP, WorkAddressSkipCallback())
        .as_markup()
    )


def avatar_keyboard() -> InlineKeyboardMarkup:
    return (
        InlineKeyboardFactory()
        .button("Загрузить", AvatarUploadCallback())
        .button(MsgKey.DELETE, AvatarDeleteCallback())
        .button(MsgKey.MAIN_MENU, MainMenuCallback())
        .as_markup()
    )


def services_keyboard(
    items: Sequence[object],
    *,
    is_accepting_orders: bool = False,
    nearby_notifications_enabled: bool = False,
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardFactory()
    if is_accepting_orders:
        keyboard.button(
            "Перестать принимать заказы",
            AcceptingOrdersCallback(value=False),
        )
    else:
        keyboard.button(
            "Начать принимать заказы",
            AcceptingOrdersCallback(value=True),
        )
    keyboard.button(
        (
            "Выключить уведомления о ближайших заказах"
            if nearby_notifications_enabled
            else "Включить уведомления о ближайших заказах"
        ),
        NearbyOrderNotificationsCallback(value=not nearby_notifications_enabled),
    )
    for index, item in enumerate(items):
        enabled = bool(getattr(item, "is_enabled", False))
        name = str(getattr(item, "service_name", f"#{index + 1}"))
        toggle_text = "Отключить" if enabled else "Включить"
        keyboard.button(f"{toggle_text}: {name}", ServiceToggleCallback(index=index))
        current_limit = int(getattr(item, "performer_max_objects", 1))
        if current_limit > 1:
            keyboard.button(f"Лимит -1: {name}", ServiceLimitCallback(index=index))
    return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()


def calendar_keyboard(
    override: CalendarOverrideDTO | None = None,
) -> InlineKeyboardMarkup:
    keyboard = (
        InlineKeyboardFactory()
        .button(
            "Каждый день 09-18",
            CalendarScheduleCallback(schedule_type="every_day"),
        )
        .button("Будни 09-18", CalendarScheduleCallback(schedule_type="weekdays"))
        .button("Выходные 09-18", CalendarScheduleCallback(schedule_type="weekends"))
        .button("Свой график", CalendarCustomScheduleCallback())
    )
    if override is None:
        keyboard.button("Добавить недоступность", CalendarUnavailableCallback())
    else:
        keyboard.button(
            "Отменить недоступность",
            CalendarCancelUnavailableCallback(override_id=str(override.id)),
        )
    return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()


__all__ = [
    "avatar_keyboard",
    "available_orders_keyboard",
    "calendar_keyboard",
    "category_select_keyboard",
    "contact_methods_keyboard",
    "direct_offer_keyboard",
    "direct_response_card_keyboard",
    "fallback_keyboard",
    "legal_acceptance_keyboard",
    "main_menu_keyboard",
    "my_order_card_keyboard",
    "my_order_card_keyboard_for_status",
    "my_orders_page_keyboard",
    "orders_filter_keyboard",
    "order_location_keyboard",
    "responses_keyboard",
    "phone_contact_keyboard",
    "registration_summary_keyboard",
    "select_city_keyboard",
    "services_keyboard",
    "stale_action_keyboard",
    "support_keyboard",
    "work_address_card_keyboard",
    "work_address_city_keyboard",
    "work_address_created_keyboard",
    "work_address_skip_keyboard",
    "work_address_suggestions_keyboard",
    "work_addresses_keyboard",
]


def _valid_telegram_url(url: str | None) -> bool:
    return isinstance(url, str) and url.startswith("https://t.me/")

from collections.abc import Sequence
from datetime import datetime
from html import escape
from typing import Protocol


class LegalDocumentView(Protocol):
    @property
    def document_type(self) -> str:
        pass

    @property
    def version(self) -> str:
        pass

    @property
    def content_url(self) -> str:
        pass


class ExecutorProfileView(Protocol):
    @property
    def full_name(self) -> str:
        pass

    @property
    def phone(self) -> str:
        pass

    @property
    def telegram_username(self) -> str | None:
        pass

    @property
    def contact_method(self) -> str:
        pass

    @property
    def city_id(self) -> object:
        pass

    @property
    def about_text(self) -> str | None:
        pass

    @property
    def status(self) -> str:
        pass

    @property
    def is_accepting_orders(self) -> bool:
        pass

    @property
    def current_address_id(self) -> object | None:
        pass


class MyOrderSummaryView(Protocol):
    @property
    def service_name(self) -> str:
        pass

    @property
    def status(self) -> str:
        pass

    @property
    def matching_mode(self) -> str | None:
        pass

    @property
    def start_at(self) -> datetime:
        pass

    @property
    def end_at(self) -> datetime:
        pass

    @property
    def objects_count(self) -> int:
        pass

    @property
    def total_amount(self) -> object:
        pass

    @property
    def payment_deadline_at(self) -> datetime | None:
        pass

    @property
    def matching_deadline_at(self) -> datetime:
        pass


class MyOrdersPageView(Protocol):
    @property
    def items(self) -> Sequence[MyOrderSummaryView]:
        pass

    @property
    def page(self) -> int:
        pass

    @property
    def total_pages(self) -> int:
        pass

    @property
    def total_items(self) -> int:
        pass


class MyOrderCardView(MyOrderSummaryView, Protocol):
    @property
    def payment_status(self) -> str | None:
        pass


def retry_later_text() -> str:
    return "⚠️ <b>Сервис временно недоступен</b>\n\nПопробуйте еще раз чуть позже."


def no_invitation_text() -> str:
    return (
        "<b>Регистрация по приглашению</b>\n\n"
        "Сейчас для вашего Telegram-аккаунта нет активного приглашения. "
        "Если вы уже общались с администратором, напишите в поддержку."
    )


def registration_unavailable_text() -> str:
    return (
        "⚠️ <b>Не удалось продолжить регистрацию</b>\n\n"
        "Попробуйте открыть бот заново командой /start."
    )


def legal_documents_text(documents: Sequence[LegalDocumentView]) -> str:
    lines = [
        "<b>Регистрация исполнителя</b>",
        "",
        "Перед началом нужно принять документы:",
    ]
    for document in documents:
        title = escape(document.document_type)
        version = escape(document.version)
        url = escape(document.content_url)
        lines.append(f"• {title} {version}: {url}")
    lines.extend(("", "Нажмите кнопку ниже, если согласны продолжить."))
    return "\n".join(lines)


def full_name_step_text() -> str:
    return "<b>Ваши данные</b>\n\nВведите ФИО текстом."


def phone_step_text() -> str:
    return (
        "<b>Телефон</b>\n\n"
        "Нажмите кнопку «Поделиться номером». Ввод телефона текстом не принимается."
    )


def invalid_phone_contact_text() -> str:
    return (
        "<b>Нужен номер из Telegram</b>\n\n"
        "Нажмите кнопку «Поделиться номером» под сообщением."
    )


def wrong_phone_contact_text() -> str:
    return (
        "<b>Нужен ваш номер</b>\n\n"
        "Telegram прислал контакт другого пользователя. Поделитесь своим номером "
        "кнопкой под сообщением."
    )


def phone_contact_received_text() -> str:
    return "Номер получен."


def select_city_text() -> str:
    return "<b>Город работы</b>\n\nВыберите город, где готовы выполнять заказы."


def select_contact_method_text() -> str:
    return "<b>Предпочтительный контакт</b>\n\nВыберите удобный способ связи."


def about_step_text() -> str:
    return (
        "<b>О себе</b>\n\n"
        "Коротко расскажите об опыте. Не указывайте лишние персональные данные."
    )


def summary_text(data: dict[str, object]) -> str:
    return "\n".join(
        (
            "<b>Проверьте данные</b>",
            "",
            f"ФИО: {escape(str(data['full_name']))}",
            f"Телефон: {escape(str(data['phone']))}",
            f"Город: {escape(str(data['city_name']))}",
            f"Контакт: {escape(str(data['contact_method_label']))}",
            f"О себе: {escape(str(data['about_text']))}",
            "",
            "Если все верно, отправьте регистрацию на проверку.",
        ),
    )


CATEGORY_EMOJIS = {
    "child": "👶",
    "ward": "🧓",
    "pet": "🐾",
}


def category_select_text() -> str:
    return "<b>Выберите направление</b>"


def executor_main_menu_text(category: object | None = None) -> str:
    if category is None:
        return "<b>Главное меню</b>"
    name = str(getattr(category, "name", "Главное меню"))
    care_object_type = str(getattr(category, "care_object_type", ""))
    emoji = CATEGORY_EMOJIS.get(care_object_type, "")
    title = f"{emoji} {name}".strip()
    return f"<b>{escape(title)}</b>"


def executor_profile_text(profile: ExecutorProfileView) -> str:
    username = profile.telegram_username
    username_text = f"@{escape(username)}" if isinstance(username, str) else "не указан"
    about = profile.about_text
    about_text = escape(about) if isinstance(about, str) else "не указано"
    accepting_orders = "включен" if profile.is_accepting_orders else "выключен"
    return "\n".join(
        (
            "<b>Профиль исполнителя</b>",
            "",
            f"ФИО: {escape(profile.full_name)}",
            f"Телефон: {escape(profile.phone)}",
            f"Город ID: {escape(str(profile.city_id))}",
            f"Контакт: {escape(profile.contact_method)}",
            f"О себе: {about_text}",
            f"Telegram: {username_text}",
            f"Статус: {escape(profile.status)}",
            f"Прием заказов: {accepting_orders}",
            f"Текущий рабочий адрес ID: {escape(str(profile.current_address_id))}",
        ),
    )


def work_addresses_list_text(count: int) -> str:
    if count == 0:
        return "<b>Рабочий адрес</b>\n\nДобавьте адрес для профиля исполнителя."
    return "<b>Рабочие адреса</b>\n\nВыберите адрес или добавьте новый."


def work_address_card_text(item: object) -> str:
    address_text = escape(str(getattr(item, "address_text", "")))
    entrance = getattr(item, "entrance", None)
    floor = getattr(item, "floor", None)
    apartment = getattr(item, "apartment", None)
    comment = getattr(item, "comment", None)
    lines = ["<b>Рабочий адрес</b>", "", address_text]
    if isinstance(entrance, str):
        lines.append(f"Подъезд: {escape(entrance)}")
    if isinstance(floor, str):
        lines.append(f"Этаж: {escape(floor)}")
    if isinstance(apartment, str):
        lines.append(f"Квартира: {escape(apartment)}")
    if isinstance(comment, str):
        lines.append(f"Комментарий: {escape(comment)}")
    return "\n".join(lines)


def work_address_city_step_text() -> str:
    return "<b>Город</b>\n\nВыберите город рабочего адреса."


def work_address_query_step_text() -> str:
    return "<b>Адрес</b>\n\nВведите улицу, дом или полный адрес."


def work_address_suggestion_step_text() -> str:
    return "<b>Подсказки адреса</b>\n\nВыберите подходящий вариант."


def work_address_extra_step_text(field_name: str) -> str:
    return f"<b>{escape(field_name)}</b>\n\nВведите значение или пропустите."


def work_address_created_text() -> str:
    return "Рабочий адрес сохранен."


def work_address_deleted_text() -> str:
    return "Рабочий адрес удален."


def work_address_current_text() -> str:
    return "Текущий рабочий адрес обновлен."


def work_address_validation_error_text(message: str) -> str:
    if "DaData API key is not configured" in message:
        return (
            "<b>Адресный сервис не настроен</b>\n\n"
            "Рабочие адреса проверяются через DaData. Сейчас ключ DaData не задан."
        )
    return "<b>Адрес не принят</b>\n\nПроверьте адрес и попробуйте еще раз."


def avatar_menu_text() -> str:
    return "<b>Аватар профиля</b>\n\nЗагрузите или удалите фото профиля."


def avatar_upload_step_text() -> str:
    return "Отправьте фото или файл JPEG, PNG, WebP до 5 МБ."


def avatar_uploaded_text() -> str:
    return "Аватар сохранен."


def avatar_deleted_text() -> str:
    return "Аватар удален."


def services_text(items: Sequence[object]) -> str:
    if not items:
        return "<b>Услуги</b>\n\nПока нет одобренных услуг."
    lines = ["<b>Услуги</b>", ""]
    for item in items:
        enabled = "включена" if getattr(item, "is_enabled", False) else "выключена"
        limit = escape(str(getattr(item, "performer_max_objects", 1)))
        lines.append(
            (
                f"{escape(str(getattr(item, 'service_name', 'Услуга')))}: "
                f"{enabled}, лимит {limit}"
            ),
        )
    return "\n".join(lines)


def services_updated_text() -> str:
    return "Настройки услуг обновлены."


def calendar_text() -> str:
    return "<b>Календарь</b>\n\nВыберите шаблон или быстрое исключение."


def calendar_updated_text() -> str:
    return "Календарь обновлен."


def available_orders_placeholder_text(scope: object) -> str:
    scope_text = _order_scope_text(scope)
    return (
        "<b>Доступные заказы</b>\n\n"
        f"Фильтр: {scope_text}.\n\n"
        "Сейчас подходящих заказов нет."
    )


def available_orders_text(items: Sequence[object], scope: object) -> str:
    if not items:
        return available_orders_placeholder_text(scope)
    lines = ["<b>Доступные заказы</b>", "", f"Фильтр: {_order_scope_text(scope)}."]
    for index, item in enumerate(items, start=1):
        service = escape(str(getattr(item, "service_name", "Услуга")))
        start_at = escape(str(getattr(item, "start_at", "")))
        end_at = escape(str(getattr(item, "end_at", "")))
        amount = escape(str(getattr(item, "total_amount", "")))
        objects_count = escape(str(getattr(item, "objects_count", "")))
        lines.extend(
            (
                "",
                f"{index}. <b>{service}</b>",
                f"{start_at} - {end_at}",
                f"Объектов: {objects_count}",
                f"Сумма: {amount}",
            ),
        )
    return "\n".join(lines)


def pool_response_created_text() -> str:
    return "Отклик создан. Заказ появился в ваших откликах."


def direct_accept_created_text() -> str:
    return "Direct-заказ принят. Заказчик получил запрос на оплату."


def direct_rejected_text() -> str:
    return "Direct-приглашение отклонено."


def executor_orders_placeholder_text(scope: object) -> str:
    scope_text = _order_scope_text(scope)
    return (
        "<b>Мои заказы</b>\n\n"
        f"Фильтр: {scope_text}.\n\n"
        "Список заказов будет подключен после backend-контракта."
    )


def my_orders_page_text(page: MyOrdersPageView, group: str) -> str:
    title = "Активные заказы" if group == "active" else "Архив заказов"
    if not page.items:
        return f"<b>{title}</b>\n\nЗдесь пока нет заказов."
    total_pages = page.total_pages or 1
    lines = [
        f"<b>{title}</b>",
        f"Страница {page.page} из {total_pages}. Всего: {page.total_items}.",
    ]
    for index, item in enumerate(page.items, start=1):
        lines.extend(
            (
                "",
                f"{index}. {escape(item.service_name)}",
                f"Статус: {_order_status_label(item.status)}",
                f"Время: {_datetime_label(item.start_at)}",
                f"Сумма: {escape(str(item.total_amount))} ₽",
            ),
        )
    return "\n".join(lines)


def my_order_card_text(order: MyOrderCardView) -> str:
    lines = [
        "<b>Заказ</b>",
        "",
        f"Услуга: {escape(order.service_name)}",
        f"Статус: {_order_status_label(order.status)}",
        f"Начало: {_datetime_label(order.start_at)}",
        f"Окончание: {_datetime_label(order.end_at)}",
        f"Объектов: {order.objects_count}",
        f"Сумма заказа: {escape(str(order.total_amount))} ₽",
    ]
    if order.matching_mode is not None:
        lines.append(f"Подбор: {escape(order.matching_mode)}")
    if order.status == "searching":
        lines.append(f"Подбор до: {_datetime_label(order.matching_deadline_at)}")
    if order.payment_deadline_at is not None:
        lines.append(
            f"Оплата заказчика до: {_datetime_label(order.payment_deadline_at)}"
        )
    if order.payment_status is not None:
        lines.append(f"Платеж заказчика: {escape(order.payment_status)}")
    if order.status in {"confirmed", "in_progress", "waiting_report"}:
        lines.extend(
            (
                "",
                "Контакты и точный адрес откроются в следующем срезе contact bridge.",
            ),
        )
    return "\n".join(lines)


def stale_action_text() -> str:
    return (
        "<b>Действие устарело или уже недоступно</b>\n\n"
        "Откройте главное меню или обратитесь в поддержку."
    )


def support_text(*, label: str, telegram_url: str | None) -> str:
    if isinstance(telegram_url, str) and telegram_url.startswith("https://t.me/"):
        return f"<b>{escape(label)}</b>\n\nОткройте поддержку кнопкой ниже."
    return (
        "<b>Поддержка</b>\n\n"
        "Контакт поддержки еще не настроен. Вернитесь в главное меню или "
        "попробуйте позже."
    )


def registration_complete_text() -> str:
    return (
        "✅ <b>Регистрация отправлена</b>\n\n"
        "Администратор проверит профиль и активирует доступ."
    )


def backend_rejected_registration_text() -> str:
    return (
        "⚠️ <b>Регистрация не принята</b>\n\n"
        "Приглашение недействительно или данные требуют проверки. "
        "Начните заново командой /start."
    )


def invalid_text_input_text(expected: str) -> str:
    return f"⚠️ <b>Нужен текст</b>\n\n{escape(expected)}"


def use_buttons_text() -> str:
    return "Выберите действие кнопкой под сообщением."


def fallback_text() -> str:
    return (
        "<b>Не понял сообщение</b>\n\n"
        "Откройте главное меню или помощь. Если вы заполняете форму, используйте "
        "кнопки и подсказки последнего сообщения."
    )


def help_text() -> str:
    return (
        "<b>Помощь</b>\n\n"
        "Используйте кнопки под сообщениями. Если сценарий недоступен, вернитесь "
        "в главное меню и попробуйте позже."
    )


def unavailable_action_text() -> str:
    return (
        "<b>Раздел пока подключается</b>\n\n"
        "Это действие появится в следующих сценариях. Сейчас можно вернуться "
        "в главное меню."
    )


def _order_scope_text(scope: object) -> str:
    return "все направления" if str(scope) == "all" else "текущее направление"


def _order_status_label(status: str) -> str:
    return {
        "searching": "идет поиск",
        "waiting_payment": "ожидает оплаты",
        "confirmed": "подтвержден",
        "in_progress": "выполняется",
        "waiting_report": "ожидает отчет",
        "report_submitted": "отчет отправлен",
        "completed": "завершен",
        "cancelled": "отменен",
        "expired": "истек",
    }.get(status, escape(status))


def _datetime_label(value: datetime) -> str:
    return escape(value.strftime("%d.%m.%Y %H:%M"))


__all__ = [
    "about_step_text",
    "backend_rejected_registration_text",
    "avatar_deleted_text",
    "avatar_menu_text",
    "avatar_upload_step_text",
    "avatar_uploaded_text",
    "available_orders_placeholder_text",
    "available_orders_text",
    "calendar_text",
    "calendar_updated_text",
    "category_select_text",
    "executor_main_menu_text",
    "executor_orders_placeholder_text",
    "executor_profile_text",
    "direct_accept_created_text",
    "direct_rejected_text",
    "fallback_text",
    "full_name_step_text",
    "help_text",
    "invalid_phone_contact_text",
    "invalid_text_input_text",
    "legal_documents_text",
    "my_order_card_text",
    "my_orders_page_text",
    "no_invitation_text",
    "phone_step_text",
    "phone_contact_received_text",
    "pool_response_created_text",
    "registration_complete_text",
    "registration_unavailable_text",
    "retry_later_text",
    "select_city_text",
    "select_contact_method_text",
    "services_text",
    "services_updated_text",
    "stale_action_text",
    "summary_text",
    "support_text",
    "unavailable_action_text",
    "use_buttons_text",
    "work_address_card_text",
    "work_address_city_step_text",
    "work_address_created_text",
    "work_address_current_text",
    "work_address_deleted_text",
    "work_address_extra_step_text",
    "work_address_query_step_text",
    "work_address_suggestion_step_text",
    "work_address_validation_error_text",
    "work_addresses_list_text",
    "wrong_phone_contact_text",
]

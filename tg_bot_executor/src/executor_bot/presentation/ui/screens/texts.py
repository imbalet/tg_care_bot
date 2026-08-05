from collections.abc import Mapping, Sequence
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

    @property
    def avatar_url(self) -> str | None:
        pass


class MyOrderSummaryView(Protocol):
    @property
    def id(self) -> object:
        pass

    @property
    def service_name(self) -> str:
        pass

    @property
    def price_type(self) -> str:
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

    @property
    def customer_comment(self) -> str | None:
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


def no_available_categories_text() -> str:
    return (
        "<b>Нет доступных направлений</b>\n\n"
        "Администратор добавит направление после проверки профиля. "
        "Пожалуйста, подождите."
    )


def executor_main_menu_text(category: object | None = None) -> str:
    if category is None:
        return "<b>Главное меню</b>"
    name = str(getattr(category, "name", "Главное меню"))
    care_object_type = str(getattr(category, "care_object_type", ""))
    emoji = CATEGORY_EMOJIS.get(care_object_type, "")
    title = f"{emoji} {name}".strip()
    return f"<b>{escape(title)}</b>"


def executor_setup_hint_text(missing: tuple[str, ...]) -> str:
    lines = ["<b>Настройка профиля исполнителя</b>", ""]
    if "schedule" in missing:
        lines.append("• выберите рабочие дни и время в разделе «Календарь»;")
    if "service" in missing:
        lines.append("• включите хотя бы одну одобренную услугу в разделе «Услуги»;")
    if "address" in missing:
        lines.append("• добавьте и выберите рабочий адрес в профиле;")
    if "accepting_orders" in missing:
        lines.append("• нажмите «Начать принимать заказы» в разделе «Услуги».")
    lines.extend(["", "После этого вы начнёте получать подходящие заказы."])
    return "\n".join(lines)


def executor_profile_text(
    profile: ExecutorProfileView,
    *,
    city_name: str | None = None,
) -> str:
    username = profile.telegram_username
    username_text = f"@{escape(username)}" if isinstance(username, str) else "не указан"
    about = profile.about_text
    about_text = escape(about) if isinstance(about, str) else "не указано"
    accepting_orders = "включен" if profile.is_accepting_orders else "выключен"
    contact_method = {
        "telegram": "Telegram",
        "phone": "телефон",
        "both": "Telegram и телефон",
    }.get(profile.contact_method, profile.contact_method)
    status = {
        "active": "Активен",
        "blocked": "Заблокирован",
        "pending": "На проверке",
        "profile_pending": "Профиль на проверке",
        "deletion_pending": "Удаление запрошено",
    }.get(profile.status, escape(profile.status))
    current_address = "не выбран" if profile.current_address_id is None else "выбран"
    return "\n".join(
        (
            "<b>Профиль исполнителя</b>",
            "",
            f"ФИО: {escape(profile.full_name)}",
            f"Телефон: {escape(profile.phone)}",
            f"Город: {escape(city_name or str(profile.city_id))}",
            f"Фото: {'загружено' if profile.avatar_url else 'не загружено'}",
            f"Контакт: {escape(contact_method)}",
            f"О себе: {about_text}",
            f"Telegram: {username_text}",
            f"Статус: {escape(status)}",
            f"Прием заказов: {accepting_orders}",
            f"Текущий рабочий адрес: {current_address}",
        ),
    )


def work_addresses_list_text(items: Sequence[object]) -> str:
    count = len(items)
    if count == 0:
        return "<b>Рабочий адрес</b>\n\nДобавьте адрес для профиля исполнителя."
    lines = ["<b>Рабочие адреса</b>", "", "Выберите адрес или добавьте новый:"]
    for index, item in enumerate(items, start=1):
        marker = " · текущий" if _item_is_current(item) else ""
        address_text = (
            item.get("address_text", "")
            if isinstance(item, Mapping)
            else getattr(item, "address_text", "")
        )
        lines.append(f"{index}. {address_text}{marker}")
    return "\n".join(lines)


def work_address_card_text(item: object) -> str:
    def value(name: str) -> object:
        if isinstance(item, Mapping):
            return item.get(name)
        return getattr(item, name, None)

    address_text = escape(str(value("address_text") or ""))
    entrance = value("entrance")
    floor = value("floor")
    apartment = value("apartment")
    comment = value("comment")
    lines = ["<b>Рабочий адрес</b>", "", address_text]
    if _item_is_current(item):
        lines.append("✅ Текущий рабочий адрес")
    if isinstance(entrance, str):
        lines.append(f"Подъезд: {escape(entrance)}")
    if isinstance(floor, str):
        lines.append(f"Этаж: {escape(floor)}")
    if isinstance(apartment, str):
        lines.append(f"Квартира: {escape(apartment)}")
    if isinstance(comment, str):
        lines.append(f"Комментарий: {escape(comment)}")
    return "\n".join(lines)


def _item_is_current(item: object) -> bool:
    if isinstance(item, Mapping):
        return bool(item.get("is_current", False))
    return bool(getattr(item, "is_current", False))


def work_address_city_step_text() -> str:
    return "<b>Город</b>\n\nВыберите город рабочего адреса."


def work_address_query_step_text() -> str:
    return "<b>Адрес</b>\n\nВведите улицу, дом или полный адрес."


def work_address_suggestion_step_text(items: Sequence[object]) -> str:
    lines = ["<b>Подсказки адреса</b>", "", "Выберите подходящий вариант:"]
    lines.extend(
        f"{index}. {getattr(item, 'value', '')}"
        for index, item in enumerate(items, start=1)
    )
    return "\n".join(lines)


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


def services_text(
    items: Sequence[object],
    is_accepting_orders: bool = False,
    nearby_notifications_enabled: bool = False,
) -> str:
    notifications = "включены" if nearby_notifications_enabled else "выключены"
    if not items:
        accepting = "принимаю заказы" if is_accepting_orders else "не принимаю заказы"
        return (
            f"<b>Услуги</b>\n\nПриём заказов: {accepting}\n"
            f"Уведомления о ближайших заказах: {notifications}\n\n"
            "Пока нет одобренных услуг."
        )
    accepting = "принимаю заказы" if is_accepting_orders else "не принимаю заказы"
    lines = [
        "<b>Услуги</b>",
        "",
        f"Приём заказов: {accepting}",
        f"Уведомления о ближайших заказах: {notifications}",
        "",
    ]
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
    return "<b>Календарь</b>\n\nНастройте график или запланируйте период недоступности."


def calendar_updated_text() -> str:
    return "Календарь обновлен."


def available_orders_placeholder_text(scope: object) -> str:
    scope_text = _order_scope_text(scope)
    return (
        "<b>Доступные заказы</b>\n\n"
        f"Фильтр: {scope_text}.\n\n"
        "Сейчас подходящих заказов нет."
    )


def available_orders_setup_text(reason: str) -> str:
    messages = {
        "schedule": "Сначала выберите рабочие дни и время в разделе «Календарь».",
        "service": (
            "Сначала включите хотя бы одну одобренную услугу в разделе «Услуги»."
        ),
        "accepting": "Сначала включите «Принимать заказы» в разделе «Услуги».",
        "address": "Сначала добавьте и выберите рабочий адрес в профиле.",
        "unavailable": (
            "Сейчас вы отмечены как недоступный исполнитель. Доступные заказы "
            "появятся после окончания периода или его отмены."
        ),
    }
    return f"<b>Доступные заказы</b>\n\n{messages[reason]}"


def cancel_confirmation_text() -> str:
    return (
        "<b>Отменить заказ?</b>\n\n"
        "Подтвердите, что не сможете выполнить этот заказ. "
        "После отмены заказ будет передан в дальнейшую обработку."
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
        distance = getattr(item, "distance_km", None)
        objects_count = escape(str(getattr(item, "objects_count", "")))
        lines.extend(
            (
                "",
                f"{index}. <b>{service}</b>",
                f"{start_at} - {end_at}",
                f"Объектов: {objects_count}",
                f"Сумма: {amount}",
                (
                    f"Расстояние: {escape(str(distance))} км"
                    if distance is not None
                    else "Расстояние: недоступно (нет координат)"
                ),
            ),
        )
    return "\n".join(lines)


def pool_response_created_text() -> str:
    return "Отклик создан. Заказ появился в ваших откликах."


def direct_accept_created_text() -> str:
    return "Direct-заказ принят. Заказчик получил запрос на оплату."


def direct_rejected_text() -> str:
    return "Direct-приглашение отклонено."


def direct_conflict_text(error: str) -> str:
    lowered = error.lower()
    if "available" in lowered or "calendar" in lowered:
        return (
            "⚠️ <b>Заказ недоступен</b>\n\n"
            "Время заказа пересекается с вашей занятостью или календарём. "
            "Приглашение больше нельзя принять."
        )
    if "deadline" in lowered or "expired" in lowered:
        return "⌛ <b>Приглашение истекло</b>\n\nОтветить на него уже нельзя."
    return "⚠️ <b>Приглашение недоступно</b>\n\nЗаказ уже изменён или закрыт."


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
                f"ID: #{str(item.id)[:8]}",
                f"{index}. {escape(item.service_name)}",
                f"Статус: {_order_status_label(item.status)}",
                f"Время: {_datetime_label(item.start_at)}",
                f"Сумма: {escape(str(item.total_amount))} ₽",
            ),
        )
    return "\n".join(lines)


class ResponseCardView(Protocol):
    @property
    def order_id(self) -> object:
        pass

    @property
    def service_name(self) -> str | None:
        pass

    @property
    def starts_at(self) -> datetime:
        pass

    @property
    def ends_at(self) -> datetime:
        pass

    @property
    def response_expires_at(self) -> datetime:
        pass

    @property
    def status(self) -> str:
        pass

    @property
    def total_amount(self) -> object | None:
        pass

    @property
    def distance_km(self) -> object | None:
        pass

    @property
    def customer_comment(self) -> str | None:
        pass


def response_card_text(match: ResponseCardView) -> str:
    lines = [
        "<b>Карточка отклика</b>",
        "",
        f"Заказ: #{escape(str(match.order_id)[:8])}",
    ]
    if match.service_name is not None:
        lines.append(f"Услуга: {escape(match.service_name)}")
    lines.extend(
        (
            f"Период: {_datetime_label(match.starts_at)} — "
            f"{_datetime_label(match.ends_at)}",
            f"Ответить до: {_datetime_label(match.response_expires_at)}",
            f"Статус: {_response_status_label(match.status)}",
        ),
    )
    if match.total_amount is not None:
        lines.append(f"Сумма: {escape(str(match.total_amount))} ₽")
    if match.distance_km is not None:
        lines.append(f"Расстояние: {escape(str(match.distance_km))} км")
    if match.customer_comment:
        lines.append(f"Комментарий заказчика: {escape(match.customer_comment)}")
    return "\n".join(lines)


def _response_status_label(status: str) -> str:
    return {
        "pending": "ожидает ответа",
        "active": "активен",
        "selected": "выбран",
        "confirmed": "подтверждён",
        "rejected": "отклонён",
        "expired": "истёк",
        "cancelled": "отменён",
    }.get(status, escape(status))


def my_order_card_text(
    order: MyOrderCardView,
    *,
    category_name: str | None = None,
) -> str:
    duration_minutes = max(
        0,
        int((order.end_at - order.start_at).total_seconds() // 60),
    )
    if order.price_type == "started_24h":
        units = max(1, (duration_minutes + 24 * 60 - 1) // (24 * 60))
        duration = (
            f"{units} сутки"
            if units % 10 == 1 and units % 100 != 11
            else f"{units} суток"
        )
    else:
        hours, minutes = divmod(duration_minutes, 60)
        duration = (
            f"{hours} ч. {minutes} мин."
            if hours and minutes
            else f"{hours} ч."
            if hours
            else f"{minutes} мин."
        )
    lines = [
        "📦 <b>Заказ</b>",
        "",
        f"ID: #{str(order.id)[:8]}",
        f"Услуга: {escape(order.service_name)}",
        *(
            (f"Направление: {escape(category_name)}",)
            if category_name is not None
            else ()
        ),
        f"🔹 Статус: {_order_status_label(order.status)}",
        f"🗓 Начало: {_datetime_label(order.start_at)}",
        f"🗓 Окончание: {_datetime_label(order.end_at)}",
        f"⏱ Длительность: {duration}",
        f"Объектов: {order.objects_count}",
        f"Сумма заказа: {escape(str(order.total_amount))} ₽",
    ]
    if order.customer_comment:
        lines.append(f"Комментарий заказчика: {escape(order.customer_comment)}")
    if order.matching_mode is not None:
        lines.append(f"Подбор: {_matching_mode_label(order.matching_mode)}")
    if order.status == "searching":
        lines.append(f"Подбор до: {_datetime_label(order.matching_deadline_at)}")
    if order.payment_deadline_at is not None:
        lines.append(
            f"Оплата заказчика до: {_datetime_label(order.payment_deadline_at)}"
        )
    if order.payment_status is not None:
        lines.append(f"Платеж заказчика: {_payment_status_label(order.payment_status)}")
    if order.status in {"confirmed", "in_progress", "waiting_report"}:
        lines.extend(
            (
                "",
                "Точный адрес доступен кнопкой «Открыть адрес».",
            ),
        )
    return "\n".join(lines)


def stale_action_text() -> str:
    return (
        "<b>Действие устарело или уже недоступно</b>\n\n"
        "Откройте главное меню или обратитесь в поддержку."
    )


def start_window_unavailable_text() -> str:
    return (
        "<b>Пока нельзя начать заказ</b>\n\n"
        "Кнопка «Я на месте» доступна только в короткий промежуток "
        "времени перед началом заказа."
    )


def finish_window_unavailable_text() -> str:
    return (
        "<b>Пока нельзя завершить заказ</b>\n\n"
        "Завершение доступно только за 15 минут до планового окончания."
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


def _matching_mode_label(mode: str) -> str:
    return {"pool": "общий подбор", "direct": "прямой заказ"}.get(
        mode,
        escape(mode),
    )


def _payment_status_label(status: str) -> str:
    return {
        "created": "создаётся",
        "pending": "ожидает оплаты",
        "succeeded": "оплачен",
        "failed": "ошибка оплаты",
        "expired": "срок оплаты истёк",
        "cancelled": "отменён",
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
    "no_available_categories_text",
    "response_card_text",
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
    "start_window_unavailable_text",
    "finish_window_unavailable_text",
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

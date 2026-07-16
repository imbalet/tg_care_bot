from collections.abc import Sequence
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


class CustomerProfileView(Protocol):
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
    def status(self) -> str:
        pass


class PricePreviewView(Protocol):
    @property
    def service_name(self) -> str:
        pass

    @property
    def duration_minutes(self) -> int:
        pass

    @property
    def objects_count(self) -> int:
        pass

    @property
    def service_amount(self) -> object:
        pass

    @property
    def platform_fee_amount(self) -> object:
        pass

    @property
    def total_amount(self) -> object:
        pass


class OrderView(Protocol):
    @property
    def id(self) -> object:
        pass

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
    def total_amount(self) -> object:
        pass


class ServiceView(Protocol):
    @property
    def name(self) -> str:
        pass

    @property
    def description(self) -> str:
        pass

    @property
    def price_type(self) -> str:
        pass

    @property
    def base_price(self) -> object:
        pass

    @property
    def location_policy(self) -> str:
        pass

    @property
    def photo_policy(self) -> str:
        pass

    @property
    def schedule_policy(self) -> str:
        pass

    @property
    def allows_multiday(self) -> bool:
        pass

    @property
    def min_duration_minutes(self) -> int | None:
        pass

    @property
    def max_duration_minutes(self) -> int | None:
        pass


class ServiceCategoryView(Protocol):
    @property
    def name(self) -> str:
        pass

    @property
    def services(self) -> Sequence[ServiceView]:
        pass


def retry_later_text() -> str:
    return "⚠️ <b>Сервис временно недоступен</b>\n\nПопробуйте еще раз чуть позже."


def registration_unavailable_text() -> str:
    return (
        "⚠️ <b>Не удалось продолжить регистрацию</b>\n\n"
        "Попробуйте открыть бот заново командой /start."
    )


def legal_documents_text(documents: Sequence[LegalDocumentView]) -> str:
    lines = [
        "<b>Регистрация заказчика</b>",
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
    return "<b>Город</b>\n\nВыберите город, где будете создавать заказы."


def select_contact_method_text() -> str:
    return "<b>Предпочтительный контакт</b>\n\nВыберите удобный способ связи."


def summary_text(data: dict[str, object]) -> str:
    return "\n".join(
        (
            "<b>Проверьте данные</b>",
            "",
            f"ФИО: {escape(str(data['full_name']))}",
            f"Телефон: {escape(str(data['phone']))}",
            f"Город: {escape(str(data['city_name']))}",
            f"Контакт: {escape(str(data['contact_method_label']))}",
            "",
            "Если все верно, подтвердите регистрацию.",
        ),
    )


CATEGORY_EMOJIS = {
    "child": "👶",
    "ward": "🧓",
    "pet": "🐾",
}


def category_select_text() -> str:
    return "<b>Выберите направление</b>"


def customer_main_menu_text(category: object | None = None) -> str:
    if category is None:
        return "<b>Главное меню</b>"
    name = str(getattr(category, "name", "Главное меню"))
    care_object_type = str(getattr(category, "care_object_type", ""))
    emoji = CATEGORY_EMOJIS.get(care_object_type, "")
    title = f"{emoji} {name}".strip()
    return f"<b>{escape(title)}</b>"


def customer_profile_text(profile: CustomerProfileView) -> str:
    username = profile.telegram_username
    username_text = f"@{escape(username)}" if isinstance(username, str) else "не указан"
    return "\n".join(
        (
            "<b>Профиль заказчика</b>",
            "",
            f"ФИО: {escape(profile.full_name)}",
            f"Телефон: {escape(profile.phone)}",
            f"Город ID: {escape(str(profile.city_id))}",
            f"Контакт: {escape(profile.contact_method)}",
            f"Telegram: {username_text}",
            f"Статус: {escape(profile.status)}",
        ),
    )


def services_prices_text(category: ServiceCategoryView) -> str:
    lines = [
        f"<b>Услуги и цены: {escape(category.name)}</b>",
    ]
    if not category.services:
        lines.extend(("", "Сейчас нет активных услуг в этом направлении."))
        return "\n".join(lines)

    for service in category.services:
        lines.extend(
            (
                "",
                f"<b>{escape(service.name)}</b>",
                f"Цена: {escape(str(service.base_price))} ₽ "
                f"{_price_type_label(service.price_type)}",
                f"Длительность: {_duration_limits_text(service)}",
                f"Место: {_location_policy_label(service.location_policy)}",
                f"Расписание: {_schedule_policy_label(service.schedule_policy)}",
                f"Фотоотчет: {_photo_policy_label(service.photo_policy)}",
            ),
        )
        if service.description:
            lines.append(escape(service.description))
    return "\n".join(lines)


def care_objects_list_text(count: int, category: object | None = None) -> str:
    title = str(getattr(category, "name", "Карточки"))
    if count == 0:
        return f"<b>{escape(title)}</b>\n\nДобавьте карточку до создания заказа."
    return f"<b>{escape(title)}</b>\n\nВыберите карточку или добавьте новую."


def care_object_name_step_text(object_type_label: str) -> str:
    return f"<b>{escape(object_type_label)}</b>\n\nВведите имя или короткое название."


def care_object_age_step_text() -> str:
    return "<b>Возрастная группа</b>\n\nВыберите подходящий вариант."


def care_object_species_step_text() -> str:
    return "<b>Вид питомца</b>\n\nВведите вид: кошка, собака или другой."


def care_object_breed_step_text() -> str:
    return "<b>Порода</b>\n\nВведите породу или пропустите шаг."


def care_object_size_step_text() -> str:
    return "<b>Размер питомца</b>\n\nВыберите размер."


def care_object_mobility_step_text() -> str:
    return "<b>Помощь с передвижением</b>\n\nНужна ли помощь?"


def care_object_notes_step_text() -> str:
    return (
        "<b>Комментарий</b>\n\n"
        "Опишите режим или поведение. Не указывайте диагнозы, лекарства, "
        "медицинские документы и другие медицинские сведения."
    )


def care_object_created_text() -> str:
    return "Карточка сохранена."


def care_object_updated_text() -> str:
    return "Карточка обновлена."


def care_object_deleted_text() -> str:
    return "Карточка удалена из активного списка."


def care_object_delete_confirm_text() -> str:
    return (
        "<b>Удалить карточку?</b>\n\n"
        "Карточка будет скрыта из профиля. Если она используется в активном "
        "заказе, backend не позволит удалить ее."
    )


def delete_blocked_text(message: str) -> str:
    return validation_error_text(message)


def care_object_card_text(item: object) -> str:
    object_type = escape(str(_field(item, "object_type", "")))
    display_name = escape(str(_field(item, "display_name", "")))
    age_group = escape(str(_field(item, "age_group", "")))
    species = _field(item, "species")
    breed = _field(item, "breed")
    pet_size = _field(item, "pet_size")
    mobility = _field(item, "mobility_assistance_required")
    lines = [
        "<b>Карточка объекта ухода</b>",
        "",
        f"Тип: {object_type}",
        f"Имя: {display_name}",
        f"Возраст: {age_group}",
    ]
    if isinstance(species, str):
        lines.append(f"Вид: {escape(species)}")
    if isinstance(breed, str):
        lines.append(f"Порода: {escape(breed)}")
    if isinstance(pet_size, str):
        lines.append(f"Размер: {escape(pet_size)}")
    if isinstance(mobility, bool):
        lines.append(f"Помощь с передвижением: {'да' if mobility else 'нет'}")
    return "\n".join(lines)


def addresses_list_text(count: int) -> str:
    if count == 0:
        return "<b>Адреса</b>\n\nДобавьте адрес до создания заказа."
    return "<b>Адреса</b>\n\nВыберите адрес или добавьте новый."


def address_card_text(item: object) -> str:
    address_text = escape(str(_field(item, "address_text", "")))
    entrance = _field(item, "entrance")
    floor = _field(item, "floor")
    apartment = _field(item, "apartment")
    comment = _field(item, "comment")
    lines = ["<b>Адрес</b>", "", address_text]
    if isinstance(entrance, str):
        lines.append(f"Подъезд: {escape(entrance)}")
    if isinstance(floor, str):
        lines.append(f"Этаж: {escape(floor)}")
    if isinstance(apartment, str):
        lines.append(f"Квартира: {escape(apartment)}")
    if isinstance(comment, str):
        lines.append(f"Комментарий: {escape(comment)}")
    return "\n".join(lines)


def address_city_step_text() -> str:
    return "<b>Город</b>\n\nВыберите город адреса."


def address_query_step_text() -> str:
    return "<b>Адрес</b>\n\nВведите улицу, дом или полный адрес."


def address_suggestion_step_text() -> str:
    return "<b>Подсказки адреса</b>\n\nВыберите подходящий вариант."


def address_extra_step_text(field_name: str) -> str:
    return f"<b>{escape(field_name)}</b>\n\nВведите значение или пропустите."


def address_created_text() -> str:
    return "Адрес сохранен."


def address_deleted_text() -> str:
    return "Адрес удален из активного списка."


def address_delete_confirm_text() -> str:
    return (
        "<b>Удалить адрес?</b>\n\n"
        "Адрес будет скрыт из активного списка. Старые заказы сохранят свою "
        "историю."
    )


def address_validation_error_text(message: str) -> str:
    if "DaData API key is not configured" in message:
        return (
            "<b>Адресный сервис не настроен</b>\n\n"
            "Адреса проверяются через DaData. Сейчас ключ DaData не задан."
        )
    return validation_error_text(message)


def validation_error_text(message: str) -> str:
    text = _VALIDATION_MESSAGES.get(message)
    if text is not None:
        return text
    return (
        "<b>Данные не приняты</b>\n\nПроверьте введенные данные и попробуйте еще раз."
    )


def order_services_step_text() -> str:
    return "<b>Новый заказ</b>\n\nВыберите услугу."


def order_no_services_text() -> str:
    return "<b>Новый заказ</b>\n\nСейчас нет активных услуг для заказа."


def order_objects_step_text(*, selected_count: int = 0, max_count: int = 1) -> str:
    if max_count <= 1:
        return "<b>Кого нужно взять в работу</b>\n\nВыберите карточку объекта ухода."
    return (
        "<b>Кого нужно взять в работу</b>\n\n"
        f"Выберите до {max_count} карточек. Сейчас выбрано: {selected_count}."
    )


def order_no_objects_text(object_type: str) -> str:
    return (
        "<b>Новый заказ</b>\n\n"
        f"Нет подходящих карточек типа: {escape(object_type)}. "
        "Добавьте карточку в разделе «Объекты ухода»."
    )


def order_start_step_text() -> str:
    return "<b>Дата и время</b>\n\nВведите начало в формате ГГГГ-ММ-ДД ЧЧ:ММ."


def order_duration_step_text(*, uses_days: bool = False) -> str:
    unit = "суток" if uses_days else "часов"
    return f"<b>Длительность</b>\n\nВведите количество {unit} целым числом."


def order_address_step_text() -> str:
    return "<b>Адрес</b>\n\nВыберите адрес заказа."


def order_no_addresses_text() -> str:
    return "<b>Новый заказ</b>\n\nДобавьте адрес в разделе «Адреса»."


def order_photo_consent_step_text() -> str:
    return "<b>Фотоотчет</b>\n\nЭта услуга требует согласия на фотоотчет."


def order_comment_step_text() -> str:
    return (
        "<b>Комментарий</b>\n\n"
        "Добавьте детали для исполнителя или пропустите шаг. Не указывайте "
        "медицинские сведения."
    )


def order_draft_summary_text(
    *,
    price: PricePreviewView,
    performers_count: int,
) -> str:
    return "\n".join(
        (
            "<b>Проверьте заказ</b>",
            "",
            f"Услуга: {escape(price.service_name)}",
            f"Длительность: {price.duration_minutes} мин.",
            f"Объектов: {price.objects_count}",
            f"Услуга: {escape(str(price.service_amount))}",
            f"Комиссия: {escape(str(price.platform_fee_amount))}",
            f"Итого: {escape(str(price.total_amount))}",
            f"Подходящих исполнителей: {performers_count}",
            "",
            "Выберите способ публикации.",
        ),
    )


def order_published_text(order: OrderView) -> str:
    mode = order.matching_mode or "pool"
    return "\n".join(
        (
            "<b>Заказ опубликован</b>",
            "",
            f"ID: {escape(str(order.id))}",
            f"Услуга: {escape(order.service_name)}",
            f"Статус: {escape(order.status)}",
            f"Подбор: {escape(mode)}",
            f"Итого: {escape(str(order.total_amount))}",
        ),
    )


def invalid_datetime_text() -> str:
    return "Введите дату и время в формате ГГГГ-ММ-ДД ЧЧ:ММ."


def invalid_duration_text(*, uses_days: bool = False) -> str:
    unit = "суток" if uses_days else "часов"
    return f"Введите положительное целое количество {unit}."


def registration_complete_text() -> str:
    return "✅ <b>Регистрация завершена</b>\n\nОткрываю главное меню."


def backend_rejected_registration_text() -> str:
    return (
        "⚠️ <b>Данные не приняты</b>\n\n"
        "Проверьте регистрацию и начните заново командой /start."
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


def _price_type_label(price_type: str) -> str:
    return {
        "hourly": "за час",
        "fixed": "за услугу",
        "daily": "за сутки",
    }.get(price_type, "")


def _location_policy_label(policy: str) -> str:
    return {
        "customer_home": "у заказчика",
        "performer_home": "у исполнителя",
        "remote": "удаленно",
        "walk": "прогулка",
    }.get(policy, escape(policy))


def _photo_policy_label(policy: str) -> str:
    return {
        "none": "не нужен",
        "optional": "по желанию",
        "required": "обязателен",
    }.get(policy, escape(policy))


def _schedule_policy_label(policy: str) -> str:
    return {
        "fixed_start": "фиксированное начало",
        "flexible": "гибкое время",
        "overnight": "с ночевкой",
    }.get(policy, escape(policy))


def _duration_limits_text(service: ServiceView) -> str:
    unit = "сут." if service.allows_multiday else "ч."
    divider = 1440 if service.allows_multiday else 60
    min_value = _duration_value(service.min_duration_minutes, divider)
    max_value = _duration_value(service.max_duration_minutes, divider)
    if min_value is not None and max_value is not None:
        return f"{min_value}-{max_value} {unit}"
    if min_value is not None:
        return f"от {min_value} {unit}"
    if max_value is not None:
        return f"до {max_value} {unit}"
    return "по договоренности"


def _duration_value(minutes: int | None, divider: int) -> str | None:
    if minutes is None:
        return None
    value = minutes / divider
    if value.is_integer():
        return str(int(value))
    return str(value).rstrip("0").rstrip(".")


_VALIDATION_MESSAGES = {
    "Address was not normalized": (
        "<b>Адрес не принят</b>\n\n"
        "Выберите адрес из подсказок или уточните улицу и дом."
    ),
    "Boarding order must not use customer address": (
        "<b>Адрес не нужен</b>\n\nДля этой услуги адрес заказчика не выбирается."
    ),
    "Care object is inactive or unknown": (
        "<b>Карточка недоступна</b>\n\nВыберите другую карточку объекта ухода."
    ),
    "City is inactive or unknown": (
        "<b>Город недоступен</b>\n\nВыберите другой город."
    ),
    "Customer address is inactive or unknown": (
        "<b>Адрес недоступен</b>\n\nВыберите другой адрес."
    ),
    "Customer address is required": ("<b>Нужен адрес</b>\n\nВыберите адрес заказа."),
    "Customer cannot manage addresses": (
        "<b>Адрес не принят</b>\n\nПрофиль заказчика не может изменить этот адрес."
    ),
    "Customer cannot manage care objects": (
        "<b>Карточка не принята</b>\n\n"
        "Профиль заказчика не может изменить эту карточку."
    ),
    "DaData API key is not configured": (
        "<b>Адресный сервис не настроен</b>\n\n"
        "Адреса проверяются через DaData. Сейчас ключ DaData не задан."
    ),
    "DaData is unavailable": (
        "<b>Адресный сервис недоступен</b>\n\nПопробуйте еще раз чуть позже."
    ),
    "DaData rejected address request": (
        "<b>Адрес не принят</b>\n\nУточните адрес и попробуйте еще раз."
    ),
    "Mobility assistance is allowed only for wards": (
        "<b>Карточка не принята</b>\n\n"
        "Помощь с передвижением указывается только для подопечных."
    ),
    "Order duration is longer than service maximum": (
        "<b>Длительность слишком большая</b>\n\n"
        "Укажите меньшую длительность для выбранной услуги."
    ),
    "Order duration is shorter than service minimum": (
        "<b>Длительность слишком маленькая</b>\n\n"
        "Укажите большую длительность для выбранной услуги."
    ),
    "Order interval exceeds payment provider hold limit": (
        "<b>Период слишком длинный</b>\n\nВыберите более короткий заказ."
    ),
    "Order must include care objects": (
        "<b>Нужна карточка</b>\n\nВыберите хотя бы одну карточку объекта ухода."
    ),
    "Order start is too soon": (
        "<b>Слишком раннее начало</b>\n\n"
        "До начала заказа должно оставаться больше времени."
    ),
    "Pet fields are allowed only for pets": (
        "<b>Карточка не принята</b>\n\n"
        "Вид, порода и размер указываются только для питомцев."
    ),
    "Pet species and size are required": (
        "<b>Карточка не принята</b>\n\nДля питомца нужны вид и размер."
    ),
    "Performer is not suitable for direct order": (
        "<b>Исполнитель недоступен</b>\n\n"
        "Выберите другого исполнителя или опубликуйте заказ для всех подходящих."
    ),
    "Report photo consent is not allowed for this service": (
        "<b>Фотоотчет не нужен</b>\n\n"
        "Для этой услуги согласие на фотоотчет не требуется."
    ),
    "Report photo consent is required": (
        "<b>Нужно согласие</b>\n\nВыберите согласие на фотоотчет."
    ),
    "Unknown age group": (
        "<b>Возрастная группа не принята</b>\n\nВыберите возраст кнопкой."
    ),
    "Unknown care object type": (
        "<b>Тип карточки не принят</b>\n\nВыберите тип карточки кнопкой."
    ),
    "Unknown pet size": ("<b>Размер питомца не принят</b>\n\nВыберите размер кнопкой."),
    "Ward mobility assistance value is required": (
        "<b>Карточка не принята</b>\n\n"
        "Для подопечного нужно указать, нужна ли помощь с передвижением."
    ),
}


def _field(item: object, key: str, default: object = None) -> object:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)

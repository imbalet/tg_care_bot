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
    return "<b>Телефон</b>\n\nВведите номер телефона для связи."


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


def care_object_deleted_text() -> str:
    return "Карточка удалена из активного списка."


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


def address_validation_error_text(message: str) -> str:
    if "DaData API key is not configured" in message:
        return (
            "<b>Адресный сервис не настроен</b>\n\n"
            "Адреса проверяются через DaData. Сейчас ключ DaData не задан."
        )
    return "<b>Адрес не принят</b>\n\nПроверьте адрес и попробуйте еще раз."


def order_services_step_text() -> str:
    return "<b>Новый заказ</b>\n\nВыберите услугу."


def order_no_services_text() -> str:
    return "<b>Новый заказ</b>\n\nСейчас нет активных услуг для заказа."


def unfinished_action_text() -> str:
    return (
        "<b>Вы не завершили текущее действие.</b>\n\n"
        "Продолжите сценарий или отмените его перед сменой направления."
    )


def order_objects_step_text() -> str:
    return "<b>Кого нужно взять в работу</b>\n\nВыберите карточку объекта ухода."


def order_no_objects_text(object_type: str) -> str:
    return (
        "<b>Новый заказ</b>\n\n"
        f"Нет подходящих карточек типа: {escape(object_type)}. "
        "Добавьте карточку в разделе «Объекты ухода»."
    )


def order_start_step_text() -> str:
    return "<b>Дата и время</b>\n\nВведите начало в формате ГГГГ-ММ-ДД ЧЧ:ММ."


def order_duration_step_text() -> str:
    return "<b>Длительность</b>\n\nВведите количество часов целым числом."


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


def invalid_duration_text() -> str:
    return "Введите длительность целым числом от 1 до 24."


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


def _field(item: object, key: str, default: object = None) -> object:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)

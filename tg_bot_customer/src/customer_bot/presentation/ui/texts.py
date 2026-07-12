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


def customer_main_menu_text() -> str:
    return (
        "<b>Главное меню</b>\n\n"
        "Выберите действие. Разделы будут открываться по мере подключения сценариев."
    )


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


def care_objects_list_text(count: int) -> str:
    if count == 0:
        return (
            "<b>Объекты ухода</b>\n\n"
            "Добавьте карточки детей, подопечных или питомцев до создания заказа."
        )
    return "<b>Объекты ухода</b>\n\nВыберите карточку или добавьте новую."


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
    object_type = escape(str(getattr(item, "object_type", "")))
    display_name = escape(str(getattr(item, "display_name", "")))
    age_group = escape(str(getattr(item, "age_group", "")))
    species = getattr(item, "species", None)
    breed = getattr(item, "breed", None)
    pet_size = getattr(item, "pet_size", None)
    mobility = getattr(item, "mobility_assistance_required", None)
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


__all__ = [
    "backend_rejected_registration_text",
    "care_object_age_step_text",
    "care_object_breed_step_text",
    "care_object_card_text",
    "care_object_created_text",
    "care_object_deleted_text",
    "care_object_mobility_step_text",
    "care_object_name_step_text",
    "care_object_notes_step_text",
    "care_object_size_step_text",
    "care_object_species_step_text",
    "care_objects_list_text",
    "customer_main_menu_text",
    "customer_profile_text",
    "fallback_text",
    "full_name_step_text",
    "help_text",
    "invalid_text_input_text",
    "legal_documents_text",
    "phone_step_text",
    "registration_complete_text",
    "registration_unavailable_text",
    "retry_later_text",
    "select_city_text",
    "select_contact_method_text",
    "summary_text",
    "unavailable_action_text",
    "use_buttons_text",
]

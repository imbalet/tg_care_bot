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
    "customer_main_menu_text",
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

from html import escape
from typing import Protocol

from customer_bot.presentation.callbacks import (
    HelpCallback,
    ProfileDeletionCheckCallback,
    ProfileEditCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)


class _View(Protocol):
    @property
    def full_name(self) -> str: ...

    @property
    def phone(self) -> str: ...

    @property
    def telegram_username(self) -> str | None: ...

    @property
    def contact_method(self) -> str: ...

    @property
    def city_id(self) -> object: ...

    @property
    def city_name(self) -> str: ...

    @property
    def status(self) -> str: ...


CONTACT_METHOD_LABELS = {
    "telegram": "Telegram",
    "phone": "телефон",
    "both": "Telegram и телефон",
}

STATUS_LABELS = {
    "active": "Активен",
    "blocked": "Заблокирован",
    "pending": "На проверке",
    "deletion_pending": "Удаление запрошено",
}


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        username = self.data.telegram_username
        username_text = (
            f"@{escape(username)}" if isinstance(username, str) else "не указан"
        )
        contact = CONTACT_METHOD_LABELS.get(
            self.data.contact_method,
            self.data.contact_method,
        )
        status = STATUS_LABELS.get(self.data.status, self.data.status)
        return "\n".join(
            (
                "<b>Профиль заказчика</b>",
                "",
                f"ФИО: {escape(self.data.full_name)}",
                f"Телефон: {escape(self.data.phone)}",
                f"Город: {escape(self.data.city_name or str(self.data.city_id))}",
                f"Контакт: {escape(contact)}",
                f"Telegram: {username_text}",
                f"Статус: {escape(status)}",
            ),
        )

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        keyboard.button(
            "Проверить удаление аккаунта",
            ProfileDeletionCheckCallback(),
        )
        return (
            keyboard.button("Редактировать профиль", ProfileEditCallback())
            .button("Помощь", HelpCallback())
            .as_markup()
        )

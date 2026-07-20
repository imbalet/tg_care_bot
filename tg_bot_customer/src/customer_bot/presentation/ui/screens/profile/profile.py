from html import escape
from typing import Protocol

from customer_bot.presentation.ui.screens.common._keyboard import fallback_keyboard
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
    def status(self) -> str: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        username = self.data.telegram_username
        username_text = (
            f"@{escape(username)}" if isinstance(username, str) else "не указан"
        )
        return "\n".join(
            (
                "<b>Профиль заказчика</b>",
                "",
                f"ФИО: {escape(self.data.full_name)}",
                f"Телефон: {escape(self.data.phone)}",
                f"Город ID: {escape(str(self.data.city_id))}",
                f"Контакт: {escape(self.data.contact_method)}",
                f"Telegram: {username_text}",
                f"Статус: {escape(self.data.status)}",
            ),
        )

    def _build_keyboard(self) -> Markup:
        # TODO: добавить редактирование профиля
        return fallback_keyboard(include_main_menu=True)

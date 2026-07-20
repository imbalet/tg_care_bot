from html import escape
from typing import Protocol

from customer_bot.presentation.callbacks import (
    RegistrationConfirmCallback,
    RegistrationEditCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _View(Protocol):
    @property
    def full_name(self) -> str: ...

    @property
    def phone(self) -> str: ...

    @property
    def city_name(self) -> str: ...

    @property
    def contact_method_label(self) -> str: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return "\n".join(
            (
                "<b>Проверьте данные</b>",
                "",
                f"ФИО: {escape(str(self.data.full_name))}",
                f"Телефон: {escape(str(self.data.phone))}",
                f"Город: {escape(str(self.data.city_name))}",
                f"Контакт: {escape(str(self.data.contact_method_label))}",
                "",
                "Если все верно, подтвердите регистрацию.",
            ),
        )

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button(MsgKey.CONFIRM, RegistrationConfirmCallback())
            .button(MsgKey.EDIT, RegistrationEditCallback())
            .as_markup()
        )

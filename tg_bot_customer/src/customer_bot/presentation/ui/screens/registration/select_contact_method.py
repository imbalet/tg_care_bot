from customer_bot.presentation.callbacks import (
    RegistrationContactCallback,
)
from customer_bot.presentation.types import ContactMethod
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "<b>Предпочтительный контакт</b>\n\nВыберите удобный способ связи."

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button(
                "Telegram", RegistrationContactCallback(method=ContactMethod.TELEGRAM)
            )
            .button("Телефон", RegistrationContactCallback(method=ContactMethod.PHONE))
            .button(
                "Telegram и телефон",
                RegistrationContactCallback(method=ContactMethod.BOTH),
            )
            .as_markup()
        )

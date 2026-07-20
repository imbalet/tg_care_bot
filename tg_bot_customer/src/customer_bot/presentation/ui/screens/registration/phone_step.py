from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return (
            "<b>Телефон</b>\n\n"
            "Нажмите кнопку «Поделиться номером». Ввод телефона текстом не принимается."
        )

    def _build_keyboard(self) -> Markup:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Поделиться номером", request_contact=True)],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
            input_field_placeholder="Нажмите кнопку ниже",
        )

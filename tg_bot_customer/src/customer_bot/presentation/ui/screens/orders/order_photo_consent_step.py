from customer_bot.presentation.callbacks import (
    OrderPhotoConsentCallback,
)
from customer_bot.presentation.types import YesNoValue
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreenNoView,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return "<b>Фотоотчет</b>\n\nЭта услуга требует согласия на фотоотчет."

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button(MsgKey.ALLOW, OrderPhotoConsentCallback(value=YesNoValue.YES))
            .button(MsgKey.DENY, OrderPhotoConsentCallback(value=YesNoValue.NO))
            .as_markup()
        )

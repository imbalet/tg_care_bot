from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderDirectBackCallback,
    OrderPublishPoolCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import BaseScreenNoView, Markup


class Screen(BaseScreenNoView):
    def _build_text(self) -> str:
        return (
            "<b>Подходящих исполнителей нет</b>\n\n"
            "Можно вернуться к выбору способа публикации или опубликовать заказ."
        )

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button("Опубликовать заказ", OrderPublishPoolCallback())
            .button("Назад", OrderDirectBackCallback())
            .button("Главное меню", MainMenuCallback())
            .as_markup()
        )

from html import escape
from typing import Protocol

from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderPublishPoolCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)
from customer_bot.presentation.ui.texts.labels import MsgKey


class _View(Protocol):
    @property
    def service_name(self) -> str: ...

    @property
    def duration_minutes(self) -> int: ...

    @property
    def objects_count(self) -> int: ...

    @property
    def service_amount(self) -> object: ...

    @property
    def platform_fee_amount(self) -> object: ...

    @property
    def total_amount(self) -> object: ...

    @property
    def performers_count(self) -> int: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        return "\n".join(
            (
                "<b>Проверьте заказ</b>",
                "",
                f"Услуга: {escape(self.data.service_name)}",
                f"Длительность: {self.data.duration_minutes} мин.",
                f"Объектов: {self.data.objects_count}",
                "Опции: учтены в заказе",
                f"Услуга: {escape(str(self.data.service_amount))}",
                f"Комиссия: {escape(str(self.data.platform_fee_amount))}",
                f"Итого: {escape(str(self.data.total_amount))}",
                f"Подходящих исполнителей: {self.data.performers_count}",
                "",
                "Выберите способ публикации.",
            ),
        )

    def _build_keyboard(self) -> Markup:
        # TODO: кнопка для direct
        keyboard = InlineKeyboardFactory().button(
            MsgKey.PUBLISH_POOL, OrderPublishPoolCallback()
        )
        return keyboard.button(MsgKey.MAIN_MENU, MainMenuCallback()).as_markup()

from html import escape
from uuid import UUID

from customer_bot.application.dto import PerformerProfileDTO
from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    OrderCardOpenCallback,
)
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import BaseScreen, Markup

_PRICE_TYPE_LABELS = {
    "hourly": "за час",
    "fixed": "за услугу",
    "started_24h": "за начатые сутки",
}


class Screen(BaseScreen[PerformerProfileDTO]):
    def __init__(
        self,
        data: PerformerProfileDTO,
        *,
        back_order_id: UUID | None = None,
        back_group: str = "active",
        back_page: int = 1,
    ) -> None:
        super().__init__(data)
        self._back_order_id = back_order_id
        self._back_group = back_group
        self._back_page = back_page

    def _build_text(self) -> str:
        profile = self.data
        about = escape(profile.about_text) if profile.about_text else "Не указано"
        lines = [
            "<b>Карточка исполнителя</b>",
            "",
            f"Имя: {escape(profile.full_name)}",
            f"Город: {escape(profile.city_name)}",
            f"О себе: {about}",
            f"Фото: {'доступно' if profile.avatar_url else 'не загружено'}",
            "",
            "<b>Услуги и цены</b>",
        ]
        if not profile.services:
            lines.append("Услуги пока не указаны")
        else:
            for service in profile.services:
                price_type = _PRICE_TYPE_LABELS.get(service.price_type, "за услугу")
                lines.append(
                    f"• {escape(service.service_name)} — "
                    f"{escape(str(service.base_price))} "
                    f"({escape(price_type)}), "
                    f"до {service.performer_max_objects} объектов"
                )
        return "\n".join(lines)

    def _build_keyboard(self) -> Markup:
        keyboard = InlineKeyboardFactory()
        if self._back_order_id is not None:
            keyboard.button(
                "К заказу",
                OrderCardOpenCallback(
                    order_id=self._back_order_id,
                    group=self._back_group,
                    page=self._back_page,
                ),
            )
        return keyboard.button("Главное меню", MainMenuCallback()).as_markup()

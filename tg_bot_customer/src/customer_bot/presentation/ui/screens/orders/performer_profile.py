from html import escape

from customer_bot.application.dto import PerformerProfileDTO
from customer_bot.presentation.callbacks import MainMenuCallback
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens.screen import BaseScreen, Markup


class Screen(BaseScreen[PerformerProfileDTO]):
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
                lines.append(
                    f"• {escape(service.service_name)} — "
                    f"{escape(str(service.base_price))} "
                    f"({escape(service.price_type)}), "
                    f"до {service.performer_max_objects} объектов"
                )
        return "\n".join(lines)

    def _build_keyboard(self) -> Markup:
        return (
            InlineKeyboardFactory()
            .button("Главное меню", MainMenuCallback())
            .as_markup()
        )

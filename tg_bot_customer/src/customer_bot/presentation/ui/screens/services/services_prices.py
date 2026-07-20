from collections.abc import Sequence
from html import escape
from typing import Protocol

from customer_bot.presentation.ui.screens.common._keyboard import fallback_keyboard
from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
    Markup,
)


def _price_type_label(price_type: str) -> str:
    return {
        "hourly": "за час",
        "fixed": "за услугу",
        "daily": "за сутки",
    }.get(price_type, "")


def _location_policy_label(policy: str) -> str:
    return {
        "customer_home": "у заказчика",
        "performer_home": "у исполнителя",
        "remote": "удаленно",
        "walk": "прогулка",
    }.get(policy, escape(policy))


def _photo_policy_label(policy: str) -> str:
    return {
        "none": "не нужен",
        "optional": "по желанию",
        "required": "обязателен",
    }.get(policy, escape(policy))


def _schedule_policy_label(policy: str) -> str:
    return {
        "fixed_start": "фиксированное начало",
        "flexible": "гибкое время",
        "overnight": "с ночевкой",
    }.get(policy, escape(policy))


def _duration_limits_text(service: Service) -> str:
    unit = "сут." if service.allows_multiday else "ч."
    divider = 1440 if service.allows_multiday else 60
    min_value = _duration_value(service.min_duration_minutes, divider)
    max_value = _duration_value(service.max_duration_minutes, divider)
    if min_value is not None and max_value is not None:
        return f"{min_value}-{max_value} {unit}"
    if min_value is not None:
        return f"от {min_value} {unit}"
    if max_value is not None:
        return f"до {max_value} {unit}"
    return "по договоренности"


def _duration_value(minutes: int | None, divider: int) -> str | None:
    if minutes is None:
        return None
    value = minutes / divider
    if value.is_integer():
        return str(int(value))
    return str(value).rstrip("0").rstrip(".")


class Service(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def price_type(self) -> str: ...

    @property
    def base_price(self) -> object: ...

    @property
    def location_policy(self) -> str: ...

    @property
    def photo_policy(self) -> str: ...

    @property
    def schedule_policy(self) -> str: ...

    @property
    def allows_multiday(self) -> bool: ...

    @property
    def min_duration_minutes(self) -> int | None: ...

    @property
    def max_duration_minutes(self) -> int | None: ...


class _View(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def services(self) -> Sequence[Service]: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        lines = [
            f"<b>Услуги и цены: {escape(self.data.name)}</b>",
        ]
        if not self.data.services:
            lines.extend(("", "Сейчас нет активных услуг в этом направлении."))
            return "\n".join(lines)

        for service in self.data.services:
            lines.extend(
                (
                    "",
                    f"<b>{escape(service.name)}</b>",
                    f"Цена: {escape(str(service.base_price))} ₽ "
                    f"{_price_type_label(service.price_type)}",
                    f"Длительность: {_duration_limits_text(service)}",
                    f"Место: {_location_policy_label(service.location_policy)}",
                    f"Расписание: {_schedule_policy_label(service.schedule_policy)}",
                    f"Фотоотчет: {_photo_policy_label(service.photo_policy)}",
                ),
            )
            if service.description:
                lines.append(escape(service.description))
        return "\n".join(lines)

    def _build_keyboard(self) -> Markup:
        return fallback_keyboard(include_main_menu=True)

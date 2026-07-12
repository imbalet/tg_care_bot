from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

CONTACT_METHODS = {
    "1": ("telegram", "Telegram"),
    "2": ("phone", "Телефон"),
    "3": ("both", "Telegram и телефон"),
}


class LegalDocumentView(Protocol):
    @property
    def document_type(self) -> str:
        pass

    @property
    def version(self) -> str:
        pass

    @property
    def content_url(self) -> str:
        pass


class CityView(Protocol):
    @property
    def name(self) -> str:
        pass


def format_legal_documents(documents: Sequence[LegalDocumentView]) -> str:
    lines = ["Для регистрации нужно принять документы:"]
    for index, document in enumerate(documents, start=1):
        lines.append(
            f"{index}. {document.document_type} {document.version}: "
            f"{document.content_url}",
        )
    return "\n".join(lines)


def format_cities(cities: Sequence[CityView]) -> str:
    lines = ["Выберите город:"]
    for index, city in enumerate(cities, start=1):
        lines.append(f"{index}. {city.name}")
    return "\n".join(lines)


def format_contact_methods() -> str:
    lines = ["Выберите предпочтительный контакт:"]
    for key, (_value, label) in CONTACT_METHODS.items():
        lines.append(f"{key}. {label}")
    return "\n".join(lines)


def parse_city_choice(text: str, city_ids: list[str]) -> UUID | None:
    if not text.isdigit():
        return None
    index = int(text) - 1
    if index < 0 or index >= len(city_ids):
        return None
    return UUID(city_ids[index])


__all__ = [
    "CONTACT_METHODS",
    "format_cities",
    "format_contact_methods",
    "format_legal_documents",
    "parse_city_choice",
]

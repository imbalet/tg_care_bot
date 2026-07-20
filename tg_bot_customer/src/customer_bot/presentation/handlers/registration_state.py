from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Self
from uuid import UUID

from aiogram.fsm.state import State, StatesGroup

from customer_bot.presentation.types import ContactMethod


@dataclass(frozen=True, slots=True)
class _RegistrationCity:
    id: str
    name: str

    @classmethod
    def from_state(cls, value: object) -> Self:
        data = _mapping(value, "registration city")
        return cls(
            id=_required_str(data, "id"),
            name=_required_str(data, "name"),
        )


@dataclass(frozen=True, slots=True)
class _RegistrationLegalDocument:
    id: str
    document_type: str
    version: str
    content_url: str

    @classmethod
    def from_state(cls, value: object) -> Self:
        data = _mapping(value, "registration legal document")
        return cls(
            id=_required_str(data, "id"),
            document_type=_required_str(data, "document_type"),
            version=_required_str(data, "version"),
            content_url=_required_str(data, "content_url"),
        )


@dataclass(frozen=True, slots=True)
class _SummaryView:
    full_name: str
    phone: str
    city_name: str
    contact_method_label: str


@dataclass(frozen=True, slots=True)
class _RegistrationData:
    cities: tuple[_RegistrationCity, ...]
    legal_documents: tuple[_RegistrationLegalDocument, ...]
    full_name: str | None = None
    phone: str | None = None
    city_id: str | None = None
    city_name: str | None = None
    contact_method: ContactMethod | None = None

    @classmethod
    def from_state(cls, data: Mapping[str, object]) -> Self:
        contact_method_value = data.get("contact_method")

        return cls(
            cities=tuple(
                _RegistrationCity.from_state(item)
                for item in _sequence(data.get("cities"), "cities")
            ),
            legal_documents=tuple(
                _RegistrationLegalDocument.from_state(item)
                for item in _sequence(
                    data.get("legal_documents"),
                    "legal_documents",
                )
            ),
            full_name=_optional_str(data.get("full_name"), "full_name"),
            phone=_optional_str(data.get("phone"), "phone"),
            city_id=_optional_str(data.get("city_id"), "city_id"),
            city_name=_optional_str(data.get("city_name"), "city_name"),
            contact_method=(
                ContactMethod(contact_method_value)
                if isinstance(contact_method_value, str)
                else None
            ),
        )

    def to_state_data(self) -> dict[str, object]:
        data: dict[str, object] = asdict(self)
        if self.contact_method is not None:
            data["contact_method"] = self.contact_method.value
        return data

    def city_at(self, index: int) -> _RegistrationCity | None:
        if 0 <= index < len(self.cities):
            return self.cities[index]
        return None

    def city_by_id(self, city_id: UUID) -> _RegistrationCity | None:
        for city in self.cities:
            if city.id == str(city_id):
                return city
        return None

    def summary_view(self) -> _SummaryView:
        contact_method = _required(self.contact_method, "contact_method")
        return _SummaryView(
            full_name=_required(self.full_name, "full_name"),
            phone=_required(self.phone, "phone"),
            city_name=_required(self.city_name, "city_name"),
            contact_method_label=_contact_method_label(contact_method),
        )


class CustomerRegistration(StatesGroup):
    legal_acceptance = State()
    full_name = State()
    phone = State()
    city = State()
    contact_method = State()
    summary = State()


def _contact_method_label(contact_method: ContactMethod) -> str:
    match contact_method:
        case ContactMethod.TELEGRAM:
            return "Telegram"
        case ContactMethod.PHONE:
            return "Телефон"
        case ContactMethod.BOTH:
            return "Telegram и телефон"
        case _:
            raise ValueError(f"Unsupported contact method: {contact_method!r}")


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected {name} mapping in FSM state")
    return value


def _sequence(value: object, name: str) -> Sequence[object]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"Expected {name} sequence in FSM state")
    return value


def _required_str(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise TypeError(f"Expected {key} string in FSM state")
    return value


def _optional_str(value: object, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"Expected {name} string in FSM state")
    return value


def _required[T](value: T | None, name: str) -> T:
    if value is None:
        raise TypeError(f"Missing required registration field: {name}")
    return value


__all__ = ["CustomerRegistration", "_RegistrationData"]

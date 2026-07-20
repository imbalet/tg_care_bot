from dataclasses import dataclass
from uuid import UUID

from aiogram.fsm.state import State, StatesGroup

EXTRA_FIELDS = (
    ("entrance", "Подъезд"),
    ("floor", "Этаж"),
    ("apartment", "Квартира"),
    ("comment", "Комментарий"),
)


class AddressManagement(StatesGroup):
    city = State()
    query = State()
    suggestion = State()
    extra = State()


@dataclass(frozen=True, slots=True)
class AddressDraftSnapshot:
    city_id: UUID
    unrestricted_value: str
    entrance: str | None
    floor: str | None
    apartment: str | None
    comment: str | None

    @classmethod
    def from_data(cls, data: dict[str, object]) -> AddressDraftSnapshot:
        return cls(
            city_id=UUID(str(data["city_id"])),
            unrestricted_value=str(data["unrestricted_value"]),
            entrance=optional_str(data.get("entrance")),
            floor=optional_str(data.get("floor")),
            apartment=optional_str(data.get("apartment")),
            comment=optional_str(data.get("comment")),
        )


def address_draft(data: dict[str, object]) -> dict[str, object]:
    draft = data.get("address_draft")
    if isinstance(draft, dict):
        return dict(draft)
    raise TypeError("Expected address draft in FSM state")


def string_list(value: object) -> list[str]:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise TypeError("Expected string list in FSM state")


def optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def extra_index(draft: dict[str, object]) -> int:
    value = draft.get("extra_index", 0)
    return value if isinstance(value, int) else 0

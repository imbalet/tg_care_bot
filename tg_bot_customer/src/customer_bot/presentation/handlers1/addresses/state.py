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

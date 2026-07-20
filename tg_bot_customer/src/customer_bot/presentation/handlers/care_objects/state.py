from uuid import UUID

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from customer_bot.application.dto import CareObjectDTO


class CareObjectManagement(StatesGroup):
    name = State()
    age = State()
    species = State()
    breed = State()
    size = State()
    mobility = State()
    notes = State()
    edit_name = State()


def care_object_state(item: CareObjectDTO) -> dict[str, object]:
    return {
        "id": str(item.id),
        "object_type": item.object_type,
        "display_name": item.display_name,
        "age_group": item.age_group,
        "species": item.species,
        "breed": item.breed,
        "pet_size": item.pet_size,
        "mobility_assistance_required": item.mobility_assistance_required,
        "routine_notes": item.routine_notes,
        "behavior_notes": item.behavior_notes,
    }


async def care_object_by_index(
    state: FSMContext,
    index: int,
) -> dict[str, object] | None:
    data = await state.get_data()
    items = data.get("care_objects")
    if not isinstance(items, list):
        return None
    if index < 0 or index >= len(items):
        return None
    item = state_item(items[index])
    item["index"] = index
    return item


async def care_object_by_id(
    state: FSMContext,
    care_object_id: UUID,
) -> dict[str, object] | None:
    data = await state.get_data()
    items = data.get("care_objects")
    if not isinstance(items, list):
        return None
    for value in items:
        item = state_item(value)
        if str(item.get("id")) == str(care_object_id):
            return item
    return None


def care_object_draft(data: dict[str, object]) -> dict[str, object]:
    draft = data.get("draft")
    if isinstance(draft, dict):
        return dict(draft)
    raise TypeError("Expected care object draft in FSM state")


def state_item(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    raise TypeError("Expected care object item in FSM state")


def optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None

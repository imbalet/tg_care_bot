from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from customer_bot.application.dto import (
    CareObjectDTO,
    ServiceCategoryDTO,
    SuitablePerformerDTO,
)

LOCAL_TZ = ZoneInfo("Europe/Moscow")
MAX_DURATION_HOURS = 24


class OrderCreation(StatesGroup):
    service = State()
    object = State()
    start = State()
    duration = State()
    address = State()
    photo_consent = State()
    comment = State()
    publish = State()


def service_states(
    categories: tuple[ServiceCategoryDTO, ...],
) -> list[dict[str, object]]:
    services: list[dict[str, object]] = []
    for category in categories:
        for service in category.services:
            services.append(
                {
                    "id": str(service.id),
                    "name": service.name,
                    "category_code": category.code,
                    "category_name": category.name,
                    "care_object_type": category.care_object_type,
                    "location_policy": service.location_policy,
                    "photo_policy": service.photo_policy,
                },
            )
    return services


def care_object_state(item: CareObjectDTO) -> dict[str, object]:
    return {"id": str(item.id), "display_name": item.display_name}


def performer_state(item: SuitablePerformerDTO) -> dict[str, object]:
    return {"performer_id": str(item.performer_id), "full_name": item.full_name}


async def item_by_index(
    state: FSMContext,
    key: str,
    index: int,
) -> dict[str, object] | None:
    data = await state.get_data()
    items = data.get(key)
    if not isinstance(items, list) or index < 0 or index >= len(items):
        return None
    item = items[index]
    return item if isinstance(item, dict) else None


def parse_local_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return parsed.replace(tzinfo=LOCAL_TZ)


def parse_duration_hours(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        hours = int(value.strip())
    except ValueError:
        return None
    if hours < 1 or hours > MAX_DURATION_HOURS:
        return None
    return hours


def draft(data: dict[str, object]) -> dict[str, object]:
    draft = data.get("order_draft")
    return dict(draft) if isinstance(draft, dict) else {}


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]

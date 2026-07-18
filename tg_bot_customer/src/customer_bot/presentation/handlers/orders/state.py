from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from customer_bot.application.dto import (
    CareObjectDTO,
    ServiceCategoryDTO,
    SuitablePerformerDTO,
)

LOCAL_TZ = ZoneInfo("Europe/Moscow")


class OrderCreation(StatesGroup):
    service = State()
    object = State()
    options = State()
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
                    "max_objects_per_order": category.max_objects_per_order,
                    "price_type": service.price_type,
                    "allows_multiday": service.allows_multiday,
                    "min_duration_minutes": service.min_duration_minutes,
                    "max_duration_minutes": service.max_duration_minutes,
                    "duration_step_minutes": service.duration_step_minutes,
                    "location_policy": service.location_policy,
                    "photo_policy": service.photo_policy,
                    "options": [
                        {
                            "id": str(option.id),
                            "name": option.name,
                            "value_type": option.value_type,
                            "is_required": option.is_required,
                        }
                        for option in service.options
                    ],
                },
            )
    return services


def care_object_state(item: CareObjectDTO) -> dict[str, object]:
    return {"id": str(item.id), "display_name": item.display_name}


def selected_ids(data: dict[str, object]) -> list[str]:
    draft_data = draft(data)
    return string_list(draft_data.get("care_object_ids"))


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


def parse_local_time(value: str) -> time | None:
    try:
        return datetime.strptime(value.strip(), "%H:%M").time()
    except ValueError:
        return None


def parse_duration_interval(
    value: str | None,
    draft_data: dict[str, object],
) -> timedelta | None:
    if value is None:
        return None
    try:
        amount = int(value.strip())
    except ValueError:
        return None
    if amount < 1:
        return None
    if _uses_days(draft_data):
        return timedelta(days=amount)
    return timedelta(hours=amount)


def uses_days(draft_data: dict[str, object]) -> bool:
    return _uses_days(draft_data)


def _uses_days(draft_data: dict[str, object]) -> bool:
    return (
        draft_data.get("allows_multiday") is True
        or draft_data.get("price_type") == "started_24h"
    )


def draft(data: dict[str, object]) -> dict[str, object]:
    draft = data.get("order_draft")
    return dict(draft) if isinstance(draft, dict) else {}


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]

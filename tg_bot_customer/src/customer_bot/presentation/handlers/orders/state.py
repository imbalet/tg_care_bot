from dataclasses import dataclass
from datetime import datetime, time, timedelta
from uuid import UUID

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from customer_bot.application.dto import (
    CareObjectDTO,
    ServiceCategoryDTO,
    SuitablePerformerDTO,
)


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


@dataclass(frozen=True, slots=True)
class PerformerView:
    performer_id: UUID
    full_name: str
    service_name: str
    distance_km: object


@dataclass(frozen=True, slots=True)
class OrderSummaryView:
    service_name: str
    duration_minutes: int
    objects_count: int
    service_amount: object
    platform_fee_amount: object
    total_amount: object
    performers_count: int


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
    return {
        "performer_id": str(item.performer_id),
        "full_name": item.full_name,
        "service_name": item.service_name,
        "distance_km": str(item.distance_km) if item.distance_km is not None else None,
    }


def performer_view(value: dict[str, object]) -> PerformerView:
    distance = value.get("distance_km")
    return PerformerView(
        performer_id=UUID(str(value["performer_id"])),
        full_name=str(value["full_name"]),
        service_name=str(value.get("service_name") or "Услуга"),
        distance_km=distance,
    )


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


async def item_by_id(
    state: FSMContext,
    key: str,
    item_id: UUID,
    *,
    id_key: str = "id",
) -> dict[str, object] | None:
    data = await state.get_data()
    items = data.get(key)
    if not isinstance(items, list):
        return None
    for value in items:
        if not isinstance(value, dict):
            continue
        if str(value.get(id_key)) == str(item_id):
            return dict(value)
    return None


def parse_local_datetime(value: str) -> datetime | None:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        return None


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
    unit = duration_unit(draft_data)
    multiplier = {"days": 1440, "hours": 60, "minutes": 1}[unit]
    duration_minutes = amount * multiplier
    minimum = draft_data.get("min_duration_minutes")
    maximum = draft_data.get("max_duration_minutes")
    step = draft_data.get("duration_step_minutes")
    if isinstance(minimum, int) and duration_minutes < minimum:
        return None
    if isinstance(maximum, int) and duration_minutes > maximum:
        return None
    if isinstance(step, int) and step > 0 and duration_minutes % step != 0:
        return None
    return timedelta(minutes=duration_minutes)


def duration_unit(draft_data: dict[str, object]) -> str:
    multiday = (
        draft_data.get("allows_multiday") is True
        or draft_data.get("price_type") == "started_24h"
    )
    divisor = 1440 if multiday else 60
    for key in (
        "min_duration_minutes",
        "max_duration_minutes",
        "duration_step_minutes",
    ):
        value = draft_data.get(key)
        if isinstance(value, int) and value % divisor != 0:
            return "minutes"
    return "days" if multiday else "hours"


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

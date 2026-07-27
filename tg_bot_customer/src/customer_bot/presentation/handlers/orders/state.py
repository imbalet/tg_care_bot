from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from customer_bot.application.dto import (
    CareObjectDTO,
    ServiceCategoryDTO,
    SuitablePerformerDTO,
)
from customer_bot.presentation.view_models import PerformerView


@dataclass(frozen=True, slots=True)
class OrderDraftSnapshot:
    service_id: UUID
    start_at: datetime
    end_at: datetime
    care_object_ids: tuple[UUID, ...]
    address_id: UUID | None
    location_source: str | None
    customer_comment: str | None
    report_photo_consent: bool | None
    option_values: dict[UUID, object]

    @classmethod
    def from_data(cls, data: dict[str, object]) -> OrderDraftSnapshot:
        consent = data.get("report_photo_consent")
        raw_options = data.get("option_values")
        options = raw_options if isinstance(raw_options, dict) else {}
        raw_object_ids = data.get("care_object_ids")
        object_ids = raw_object_ids if isinstance(raw_object_ids, list) else []
        return cls(
            service_id=UUID(str(data["service_id"])),
            start_at=datetime.fromisoformat(str(data["start_at"])),
            end_at=datetime.fromisoformat(str(data["end_at"])),
            care_object_ids=tuple(UUID(str(item)) for item in object_ids),
            address_id=(
                UUID(str(data["address_id"])) if data.get("address_id") else None
            ),
            location_source=(
                str(data["location_source"]) if data.get("location_source") else None
            ),
            customer_comment=(
                str(data["customer_comment"]) if data.get("customer_comment") else None
            ),
            report_photo_consent=consent if isinstance(consent, bool) else None,
            option_values={UUID(str(key)): value for key, value in options.items()},
        )


@dataclass(frozen=True, slots=True)
class OrderSummarySnapshot:
    service_name: str
    duration_minutes: int
    objects_count: int
    service_amount: Decimal
    platform_fee_amount: Decimal
    total_amount: Decimal
    performers_count: int
    duration_unit: str = "minutes"
    start_at: datetime | None = None
    end_at: datetime | None = None
    location_label: str = "По адресу заказчика"

    @classmethod
    def from_data(cls, data: dict[str, object]) -> OrderSummarySnapshot:
        return cls(
            service_name=str(data["service_name"]),
            duration_minutes=int(str(data["duration_minutes"])),
            objects_count=int(str(data["objects_count"])),
            service_amount=Decimal(str(data["service_amount"])),
            platform_fee_amount=Decimal(str(data["platform_fee_amount"])),
            total_amount=Decimal(str(data["total_amount"])),
            performers_count=int(str(data["performers_count"])),
            duration_unit=str(data.get("duration_unit", "minutes")),
            start_at=(
                datetime.fromisoformat(str(data["start_at"]))
                if data.get("start_at")
                else None
            ),
            end_at=(
                datetime.fromisoformat(str(data["end_at"]))
                if data.get("end_at")
                else None
            ),
            location_label=str(data.get("location_label", "По адресу заказчика")),
        )

    def to_data(self) -> dict[str, object]:
        return {
            "service_name": self.service_name,
            "duration_minutes": self.duration_minutes,
            "objects_count": self.objects_count,
            "service_amount": str(self.service_amount),
            "platform_fee_amount": str(self.platform_fee_amount),
            "total_amount": str(self.total_amount),
            "performers_count": self.performers_count,
            "duration_unit": self.duration_unit,
            "start_at": self.start_at.isoformat() if self.start_at else None,
            "end_at": self.end_at.isoformat() if self.end_at else None,
            "location_label": self.location_label,
        }


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
        distance_km=Decimal(str(distance)) if distance is not None else None,
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


def start_is_valid(start_at: datetime, *, now: datetime | None = None) -> bool:
    current = now or datetime.now()
    return start_at >= current + timedelta(hours=6)


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

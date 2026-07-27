from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class PerformerScheduleDTO:
    id: UUID
    performer_id: UUID
    schedule_type: str
    work_days: tuple[int, ...] | None
    work_start_time: time
    work_end_time: time
    is_active: bool


@dataclass(frozen=True)
class CalendarOverrideDTO:
    id: UUID
    performer_id: UUID
    override_type: str
    starts_at: datetime
    ends_at: datetime
    comment: str | None
    timezone: str
    is_active: bool


@dataclass(frozen=True)
class BusyIntervalDTO:
    id: UUID
    kind: str
    status: str
    starts_at: datetime
    ends_at: datetime
    timezone: str


@dataclass(frozen=True)
class AvailabilityCheckDTO:
    performer_id: UUID
    is_available: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SuitablePerformerDTO:
    performer_id: UUID
    full_name: str
    service_id: UUID
    service_code: str
    service_name: str
    performer_max_objects: int
    distance_km: Decimal | None
    current_address_id: UUID | None

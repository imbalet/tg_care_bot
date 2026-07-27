from datetime import datetime, time
from decimal import Decimal

from pydantic import BaseModel, Field


class SetScheduleRequest(BaseModel):
    schedule_type: str
    work_days: list[int] | None = None
    work_start_time: time
    work_end_time: time


class AddOverrideRequest(BaseModel):
    override_type: str
    starts_at: datetime
    ends_at: datetime
    comment: str | None = Field(default=None, max_length=500)


class ScheduleResponse(BaseModel):
    id: str
    performer_id: str
    schedule_type: str
    work_days: list[int] | None
    work_start_time: str
    work_end_time: str
    is_active: bool


class CalendarOverrideResponse(BaseModel):
    id: str
    performer_id: str
    override_type: str
    starts_at: str
    ends_at: str
    comment: str | None
    timezone: str
    is_active: bool


class BusyIntervalResponse(BaseModel):
    id: str
    kind: str
    status: str
    starts_at: str
    ends_at: str


class CalendarResponse(BaseModel):
    schedule: ScheduleResponse | None
    overrides: list[CalendarOverrideResponse]
    busy_intervals: list[BusyIntervalResponse]


class AvailabilityCheckResponse(BaseModel):
    performer_id: str
    is_available: bool
    reasons: list[str]


class SuitablePerformerResponse(BaseModel):
    performer_id: str
    full_name: str
    service_id: str
    service_code: str
    service_name: str
    performer_max_objects: int
    distance_km: Decimal | None
    current_address_id: str | None

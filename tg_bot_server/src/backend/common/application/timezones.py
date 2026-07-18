from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.common.domain import ValidationError


def parse_timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError("City timezone is invalid") from exc


def to_utc(value: datetime, timezone: str) -> datetime:
    zone = parse_timezone(timezone)
    if value.tzinfo is None:
        return value.replace(tzinfo=zone).astimezone(UTC)
    return value.astimezone(UTC)


def to_timezone(value: datetime, timezone: str) -> datetime:
    zone = parse_timezone(timezone)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(zone)

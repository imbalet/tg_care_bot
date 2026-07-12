from datetime import UTC, datetime
from uuid import UUID

from backend.common.application import (
    Clock,
    QueryService,
    Repository,
    SystemClock,
    new_uuid,
    utc_now,
)


def test_utc_now_returns_timezone_aware_utc_datetime() -> None:
    value = utc_now()

    assert value.tzinfo is UTC
    assert value.utcoffset() == UTC.utcoffset(value)


def test_system_clock_returns_timezone_aware_utc_datetime() -> None:
    clock = SystemClock()

    value = clock.now()

    assert value.tzinfo is UTC
    assert value.utcoffset() == UTC.utcoffset(value)


def test_new_uuid_returns_distinct_uuid_values() -> None:
    first = new_uuid()
    second = new_uuid()

    assert isinstance(first, UUID)
    assert isinstance(second, UUID)
    assert first != second


def test_common_contracts_are_publicly_importable() -> None:
    assert Clock is not None
    assert QueryService is not None
    assert Repository is not None
    assert SystemClock is not None
    assert isinstance(utc_now(), datetime)

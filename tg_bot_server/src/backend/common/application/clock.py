from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        pass


class SystemClock:
    def now(self) -> datetime:
        return utc_now()


def utc_now() -> datetime:
    return datetime.now(UTC)

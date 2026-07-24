from datetime import UTC, datetime

from customer_bot.presentation.handlers.orders.creation_navigation import current_date


def test_current_date_uses_city_timezone() -> None:
    now = datetime(2026, 7, 23, 20, 30, tzinfo=UTC)

    assert current_date("Asia/Vladivostok", now=now).isoformat() == "2026-07-24"
    assert current_date("Europe/Moscow", now=now).isoformat() == "2026-07-23"

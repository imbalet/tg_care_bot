from datetime import datetime, timedelta

from customer_bot.presentation.handlers.orders.state import start_is_valid


def test_start_must_be_at_least_six_hours_ahead() -> None:
    now = datetime(2026, 7, 23, 12, 0)

    assert not start_is_valid(now + timedelta(hours=5, minutes=59), now=now)
    assert start_is_valid(now + timedelta(hours=6), now=now)

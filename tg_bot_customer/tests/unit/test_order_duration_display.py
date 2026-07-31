from customer_bot.presentation.handlers.orders.state import duration_unit
from customer_bot.presentation.ui.screens.orders.order_draft_summary import (
    duration_label,
)


def test_duration_label_formats_full_hours() -> None:
    assert duration_label(120) == "2 ч."


def test_duration_label_formats_hours_and_minutes() -> None:
    assert duration_label(90) == "1 ч. 30 мин."


def test_duration_label_formats_minutes_and_clamps_negative_values() -> None:
    assert duration_label(45) == "45 мин."
    assert duration_label(-1) == "0 мин."


def test_duration_label_formats_boarding_as_started_days() -> None:
    assert duration_label(24 * 60, "days") == "1 сутки"
    assert duration_label(24 * 60 + 1, "days") == "2 суток"


def test_boarding_duration_input_uses_days_even_with_hourly_step() -> None:
    assert (
        duration_unit(
            {
                "price_type": "started_24h",
                "allows_multiday": True,
                "duration_step_minutes": 60,
            },
        )
        == "days"
    )

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

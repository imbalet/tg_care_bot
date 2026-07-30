import pytest

from customer_bot.presentation.handlers.support import _complaint_category


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("проблема с заказом", "order_problem"),
        ("нет связи", "no_contact"),
        ("conditions_mismatch", "conditions_mismatch"),
        ("неизвестная категория", "order_problem"),
    ),
)
def test_complaint_category_is_backend_compatible(value: str, expected: str) -> None:
    assert _complaint_category(value) == expected

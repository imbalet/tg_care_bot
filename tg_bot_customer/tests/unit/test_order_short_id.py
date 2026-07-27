from uuid import UUID

from customer_bot.presentation.ui.screens.orders.status_labels import short_order_id


def test_short_order_id_uses_hash_and_first_eight_characters() -> None:
    order_id = UUID("12345678-1234-1234-1234-123456789abc")

    assert short_order_id(order_id) == "#12345678"

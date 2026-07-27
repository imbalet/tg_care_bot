from datetime import UTC, datetime
from uuid import uuid4

from customer_bot.presentation.ui.screens.orders.payment_status import Screen
from customer_bot.presentation.view_models import PaymentStatusView


def test_payment_status_screen_displays_confirmation_url_and_retry_state() -> None:
    order_id = uuid4()
    screen = Screen(
        PaymentStatusView(
            id=order_id,
            order_status="waiting_payment",
            payment_status="pending",
            confirmation_url="http://localhost:18080/pay/5",
            expires_at=datetime(2026, 7, 27, 12, 0, tzinfo=UTC),
            failure_code=None,
            attempts_used=1,
            max_attempts=3,
            retry_available=False,
        ),
    ).build()

    assert "http://localhost:18080/pay/5" in screen.text
    assert "Попытки оплаты: 1 из 3" in screen.text

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from customer_bot.presentation.ui.screens.orders.my_order_card import (
    Screen as OrderCardScreen,
)
from customer_bot.presentation.ui.screens.orders.payment_status import Screen
from customer_bot.presentation.view_models import MyOrderCardView, PaymentStatusView


def _order_card(
    *,
    payment_status: str | None,
    payment_confirmation_url: str | None,
    payment_retry_available: bool,
) -> MyOrderCardView:
    return MyOrderCardView(
        id=uuid4(),
        category_name="Няни",
        service_name="Присмотр за ребенком",
        matching_mode="pool",
        status="waiting_payment",
        start_at=datetime(2026, 7, 27, 12, 0, tzinfo=UTC),
        end_at=datetime(2026, 7, 27, 13, 0, tzinfo=UTC),
        objects_count=1,
        total_amount=Decimal("1000.00"),
        payment_deadline_at=datetime(2026, 7, 27, 12, 30, tzinfo=UTC),
        matching_deadline_at=datetime(2026, 7, 27, 11, 0, tzinfo=UTC),
        payment_status=payment_status,
        payment_confirmation_url=payment_confirmation_url,
        payment_expires_at=datetime(2026, 7, 27, 12, 30, tzinfo=UTC),
        payment_attempts_used=1,
        payment_max_attempts=3,
        payment_retry_available=payment_retry_available,
        group="active",
        page=1,
    )


def _button_texts(screen: object) -> list[str]:
    result = screen.build()
    assert result.reply_markup is not None
    return [
        button.text
        for row in result.reply_markup.inline_keyboard
        for button in row
        if button.text is not None
    ]


def test_order_card_shows_pay_button_for_pending_payment() -> None:
    texts = _button_texts(
        OrderCardScreen(
            _order_card(
                payment_status="pending",
                payment_confirmation_url="http://localhost:18080/pay/5",
                payment_retry_available=False,
            ),
        ),
    )

    assert "Оплатить" in texts
    assert "Повторить оплату" not in texts


def test_order_card_shows_retry_button_for_failed_payment() -> None:
    texts = _button_texts(
        OrderCardScreen(
            _order_card(
                payment_status="failed",
                payment_confirmation_url=None,
                payment_retry_available=True,
            ),
        ),
    )

    assert "Повторить оплату" in texts
    assert "Оплатить" not in texts


def test_order_card_hides_retry_button_when_backend_disallows_retry() -> None:
    texts = _button_texts(
        OrderCardScreen(
            _order_card(
                payment_status="failed",
                payment_confirmation_url=None,
                payment_retry_available=False,
            ),
        ),
    )

    assert "Повторить оплату" not in texts


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

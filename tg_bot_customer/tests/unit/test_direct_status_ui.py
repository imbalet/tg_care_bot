from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from customer_bot.presentation.ui.screens.orders.my_order_card import (
    Screen as MyOrderCardScreen,
)
from customer_bot.presentation.ui.screens.orders.my_orders_page import (
    Screen as MyOrdersPageScreen,
)
from customer_bot.presentation.ui.screens.orders.order_published import (
    Screen as OrderPublishedScreen,
)
from customer_bot.presentation.ui.screens.orders.status_labels import order_status_label
from customer_bot.presentation.view_models import (
    MyOrderCardView,
    MyOrdersPageView,
    OrderListItemView,
)

_START_AT = datetime(2026, 7, 31, 12, tzinfo=UTC)
_END_AT = datetime(2026, 7, 31, 13, tzinfo=UTC)


def test_direct_searching_status_is_specific_to_direct_matching() -> None:
    assert (
        order_status_label("searching", "direct") == "исполнитель рассматривает заказ"
    )
    assert order_status_label("searching", "pool") == "идёт поиск исполнителя"


def test_published_direct_order_shows_executor_review_status() -> None:
    screen = OrderPublishedScreen(
        SimpleNamespace(
            id=uuid4(),
            service_name="Присмотр за питомцем",
            status="searching",
            matching_mode="direct",
            total_amount=Decimal("1000.00"),
        ),
    ).build()

    assert "Статус: исполнитель рассматривает заказ" in screen.text
    assert "идёт поиск исполнителя" not in screen.text


def test_order_list_direct_order_shows_executor_review_status() -> None:
    item = OrderListItemView(
        id=uuid4(),
        category_code="pet",
        category_name="Животные",
        service_name="Присмотр за питомцем",
        matching_mode="direct",
        status="searching",
        start_at=_START_AT,
        end_at=_END_AT,
        objects_count=1,
        total_amount=Decimal("1000.00"),
        payment_deadline_at=None,
        matching_deadline_at=_START_AT,
    )
    screen = MyOrdersPageScreen(
        MyOrdersPageView(
            items=(item,),
            page=1,
            total_pages=1,
            total_items=1,
            group="active",
            category_code=None,
            active_category_code=None,
            active_category_name=None,
        ),
    ).build()

    assert "Статус: исполнитель рассматривает заказ" in screen.text


def test_order_card_direct_order_shows_executor_review_status() -> None:
    screen = MyOrderCardScreen(
        MyOrderCardView(
            id=uuid4(),
            category_name="Животные",
            service_name="Присмотр за питомцем",
            matching_mode="direct",
            status="searching",
            start_at=_START_AT,
            end_at=_END_AT,
            objects_count=1,
            total_amount=Decimal("1000.00"),
            payment_deadline_at=None,
            matching_deadline_at=_START_AT,
            payment_status=None,
            payment_confirmation_url=None,
            payment_expires_at=None,
            payment_attempts_used=0,
            payment_max_attempts=3,
            payment_retry_available=False,
            group="active",
            page=1,
        ),
    ).build()

    assert "🔹 Статус: исполнитель рассматривает заказ" in screen.text

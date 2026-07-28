from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.common.application.timezones import parse_timezone, to_timezone, to_utc
from backend.common.domain import ValidationError
from backend.modules.catalog.application.dto import (
    CatalogDTO,
    CityDTO,
    LegalDocumentDTO,
    ServiceCategoryDTO,
    ServiceDTO,
    ServiceOptionDTO,
    SupportContactDTO,
)
from backend.modules.catalog.presentation.api.mappers import (
    catalog_response,
    city_response,
    legal_document_response,
    service_category_response,
    support_contact_response,
)
from backend.modules.customers.application.dto import CustomerDTO
from backend.modules.customers.presentation.api.mappers import customer_response
from backend.modules.notifications.application.registry import (
    notification_action_entity_id,
    notification_actions,
    notification_body,
)
from backend.modules.orders.application.dto import (
    FullAddressSnapshotDTO,
    MyOrderCardDTO,
    MyOrdersPageDTO,
    MyOrderSummaryDTO,
    OrderDTO,
    OrderLocationDTO,
    OrderMatchDTO,
    OrderReportDTO,
    PaymentPromptDTO,
    PricePreviewDTO,
)
from backend.modules.orders.presentation.api.mappers import (
    match_response,
    my_order_card_response,
    my_orders_page_response,
    order_location_response,
    order_response,
    payment_prompt_response,
    price_preview_response,
    report_response,
)


def _times() -> tuple[datetime, datetime]:
    start = datetime(2026, 1, 2, 10, tzinfo=UTC)
    return start, start + timedelta(hours=1)


def _order() -> OrderDTO:
    start, end = _times()
    return OrderDTO(
        id=uuid4(),
        customer_id=uuid4(),
        service_id=uuid4(),
        service_code="care",
        service_name="Care",
        schedule_policy="working_hours",
        photo_policy="not_allowed",
        matching_mode="pool",
        status="searching",
        address_id=uuid4(),
        location_source="customer_address",
        start_at=start,
        end_at=end,
        objects_count=1,
        total_amount=Decimal("600.00"),
        performer_amount=Decimal("540.00"),
        platform_fee_amount=Decimal("60.00"),
        matching_deadline_at=start - timedelta(minutes=30),
        timezone="Europe/Moscow",
    )


@pytest.mark.unit
def test_catalog_and_customer_mappers_preserve_public_contract() -> None:
    city = CityDTO(uuid4(), "Moscow", "moscow", "Europe/Moscow", True)
    option = ServiceOptionDTO(uuid4(), "walk", "Walk", "bool", False, 1)
    service = ServiceDTO(
        id=uuid4(),
        code="care",
        name="Care",
        description="Description",
        price_type="fixed",
        base_price=Decimal("100"),
        location_policy="customer_address",
        photo_policy="not_allowed",
        schedule_policy="working_hours",
        allows_multiday=False,
        min_duration_minutes=None,
        max_duration_minutes=None,
        duration_step_minutes=None,
        is_active=True,
        sort_order=1,
        options=(option,),
    )
    category = ServiceCategoryDTO(
        id=uuid4(),
        code="pets",
        name="Pets",
        care_object_type="pet",
        max_objects_per_order=3,
        is_active=True,
        sort_order=1,
        services=(service,),
    )
    catalog = catalog_response(CatalogDTO((category,)))
    assert catalog.categories[0].services[0].options[0].code == "walk"
    assert city_response(city).slug == "moscow"
    assert service_category_response(category).code == "pets"
    assert (
        support_contact_response(SupportContactDTO("Support", "tg://support")).label
        == "Support"
    )
    document = LegalDocumentDTO(
        id=uuid4(),
        document_type="terms",
        version="1",
        content_url="https://docs.test/terms",
        is_active=True,
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert legal_document_response(document).content_url.endswith("terms")
    customer = CustomerDTO(
        id=uuid4(),
        telegram_id=1,
        full_name="Customer",
        phone="+79990000000",
        telegram_username=None,
        contact_method="telegram",
        city_id=city.id,
        status="active",
    )
    assert customer_response(customer).telegram_id == 1


@pytest.mark.unit
def test_order_mappers_cover_location_match_report_payment_and_pages() -> None:
    order = _order()
    assert order_response(order).id == str(order.id)
    address = FullAddressSnapshotDTO(
        city_name="Moscow",
        district_name="Center",
        address_text="Main street, 1",
        fias_id=None,
        latitude=None,
        longitude=None,
        geocoding_provider="fake",
        geocoding_quality="high",
        entrance=None,
        floor=None,
        apartment=None,
        comment=None,
    )
    location = OrderLocationDTO(order.id, "Moscow", "Center", address)
    assert order_location_response(location).address is not None
    start, end = _times()
    match = OrderMatchDTO(
        id=uuid4(),
        order_id=order.id,
        performer_id=uuid4(),
        source="pool",
        status="active",
        starts_at=start,
        ends_at=end,
        response_expires_at=end,
        selected_at=start,
        closed_at=None,
        close_reason=None,
        timezone="UTC",
    )
    assert match_response(match).selected_at is not None
    report = OrderReportDTO(
        id=uuid4(),
        order_id=order.id,
        performer_id=match.performer_id,
        completed_work="Done",
        comment=None,
        problem_flag=False,
        problem_description=None,
        submitted_at=start,
        file_ids=(uuid4(),),
    )
    assert len(report_response(report).file_ids) == 1
    payment = PaymentPromptDTO(uuid4(), "https://pay.test", end, "UTC")
    assert payment_prompt_response(payment).confirmation_url == "https://pay.test"
    summary = MyOrderSummaryDTO(
        id=order.id,
        category_code="nanny",
        service_name="Care",
        matching_mode="pool",
        status="confirmed",
        start_at=start,
        end_at=end,
        objects_count=1,
        total_amount=Decimal("10"),
        payment_deadline_at=None,
        matching_deadline_at=start,
        timezone="UTC",
    )
    card = MyOrderCardDTO(
        **summary.__dict__,
        payment_status="pending",
        payment_confirmation_url=None,
        payment_expires_at=None,
    )
    assert my_order_card_response(card).payment_status == "pending"
    page = MyOrdersPageDTO((summary,), 1, 5, 1, 1)
    assert my_orders_page_response(page).total_items == 1


@pytest.mark.unit
def test_notification_registry_and_timezone_rules_are_deterministic() -> None:
    entity_id = str(uuid4())
    actions = notification_actions("direct_invitation_created", entity_id)
    assert actions is not None
    callback_data = actions[0][0]["callback_data"]
    assert isinstance(callback_data, str)
    assert callback_data.startswith("direct_accept:")
    assert notification_actions("direct_invitation_created", "invalid") is None
    assert notification_actions("unknown", entity_id) is None
    payment_failed_actions = notification_actions("payment_failed", entity_id)
    assert payment_failed_actions == [
        [
            {
                "text": "Открыть заказ",
                "callback_data": f"notification_order:{entity_id}",
            },
        ],
    ]
    assert (
        notification_action_entity_id(
            "direct_invitation_created",
            {"match_id": entity_id},
        )
        == entity_id
    )
    assert (
        notification_action_entity_id("payment_success", {"order_id": entity_id})
        == entity_id
    )
    assert notification_body("unknown_event") == "unknown_event"
    assert "попробуйте оплатить ещё раз" in notification_body("payment_failed")
    assert "не выполнен автоматически" in notification_body("refund_failed")
    assert "администратору" in notification_body("refund_failed")
    assert parse_timezone("Europe/Moscow").key == "Europe/Moscow"
    naive = datetime(2026, 1, 1, 10)
    assert to_utc(naive, "Europe/Moscow").tzinfo == UTC
    assert to_timezone(naive, "Europe/Moscow").hour == 13
    with pytest.raises(ValidationError):
        parse_timezone("invalid/timezone")


@pytest.mark.unit
def test_price_preview_mapper_keeps_money_breakdown() -> None:
    preview = PricePreviewDTO(
        service_id=uuid4(),
        service_code="care",
        service_name="Care",
        price_type="started_24h",
        duration_minutes=1440,
        billable_minutes=None,
        started_24h_units=1,
        objects_count=1,
        object_multiplier=Decimal("1"),
        base_price=Decimal("100"),
        service_amount=Decimal("100"),
        platform_fee_percent=Decimal("10"),
        platform_fee_amount=Decimal("10"),
        performer_amount=Decimal("90"),
        total_amount=Decimal("100"),
        hold_limit_checked=True,
    )
    response = price_preview_response(preview)
    assert response.started_24h_units == 1

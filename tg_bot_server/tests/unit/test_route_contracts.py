import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import Response
from starlette.requests import Request

from backend.modules.admin.presentation.api import routes as admin_routes
from backend.modules.admin.presentation.api.schemas import (
    LoginRequest,
    ManualRefundRequest,
    MarkAdminNotificationsReadRequest,
    UpdateBusinessSettingRequest,
)
from backend.modules.availability.application.dto import (
    AvailabilityCheckDTO,
    CalendarOverrideDTO,
    PerformerScheduleDTO,
    SuitablePerformerDTO,
)
from backend.modules.availability.presentation.api import routes as availability_routes
from backend.modules.availability.presentation.api.schemas import (
    AddOverrideRequest,
    SetScheduleRequest,
)
from backend.modules.catalog.presentation.api import routes as catalog_routes
from backend.modules.customers.presentation.api import routes as customer_routes
from backend.modules.customers.presentation.api.schemas import (
    CareObjectRequest,
    CreateAddressRequest,
    CreateCareObjectRequest,
    RegisterCustomerRequest,
    UpdateTelegramUsernameRequest,
)
from backend.modules.orders.application.dto import (
    MatchActionDTO,
    OrderDTO,
    OrderMatchDTO,
    OrderReportDTO,
    PaymentPromptDTO,
    PricePreviewDTO,
)
from backend.modules.orders.presentation.api import routes as order_routes
from backend.modules.orders.presentation.api.schemas import (
    CancelOrderRequest,
    CustomerDirectPerformerRequest,
    CustomerMatchActionRequest,
    DirectOrderRequest,
    OrderReportRequest,
    OrderRequest,
    PerformerMatchActionRequest,
    PerformerOrderActionRequest,
    PricePreviewRequest,
)
from backend.modules.payments.infrastructure.gateway import _sign_payload
from backend.modules.payments.presentation.api.routes import (
    _paid_at,
    _safe_payload,
    tbank_webhook,
)
from backend.modules.performers.presentation.api import routes as performer_routes
from backend.modules.performers.presentation.api.schemas import (
    RegisterPerformerRequest,
    SetAcceptingOrdersRequest,
    SetPerformerServiceEnabledRequest,
    SetPerformerServiceMaxObjectsRequest,
)
from backend.modules.performers.presentation.api.schemas import (
    UpdateTelegramUsernameRequest as PerformerUsernameRequest,
)
from backend.modules.support.presentation.api.routes import _admin_list, _user_list


def _order() -> OrderDTO:
    start = datetime(2026, 1, 2, 10, tzinfo=UTC)
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
        address_id=None,
        location_source="customer_address",
        start_at=start,
        end_at=start + timedelta(hours=1),
        objects_count=1,
        total_amount=Decimal("100"),
        performer_amount=Decimal("90"),
        platform_fee_amount=Decimal("10"),
        matching_deadline_at=start,
        timezone="UTC",
    )


def _match(order: OrderDTO) -> OrderMatchDTO:
    return OrderMatchDTO(
        id=uuid4(),
        order_id=order.id,
        performer_id=uuid4(),
        source="pool",
        status="active",
        starts_at=order.start_at,
        ends_at=order.end_at,
        response_expires_at=order.end_at,
        selected_at=None,
        closed_at=None,
        close_reason=None,
        timezone="UTC",
    )


@pytest.mark.unit
async def test_order_routes_forward_pool_direct_matching_and_lifecycle_commands() -> (
    None
):
    service: Any = SimpleNamespace()
    service.orders = SimpleNamespace()
    order = _order()
    match = _match(order)
    report = OrderReportDTO(
        id=uuid4(),
        order_id=order.id,
        performer_id=match.performer_id,
        completed_work="Done",
        comment=None,
        problem_flag=False,
        problem_description=None,
        submitted_at=datetime.now(UTC),
        file_ids=(),
    )
    preview = PricePreviewDTO(
        service_id=order.service_id,
        service_code="care",
        service_name="Care",
        price_type="hourly",
        duration_minutes=60,
        billable_minutes=60,
        started_24h_units=None,
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
    action = MatchActionDTO(
        order=order,
        match=match,
        payment=PaymentPromptDTO(uuid4(), "https://pay.test", order.end_at, "UTC"),
    )
    for name, result in (
        ("create_pool_order", order),
        ("create_direct_order", order),
        ("publish_pool_order", order),
        ("start_order", order),
        ("finish_order", order),
        ("cancel_order", order),
    ):
        setattr(service.orders, name, AsyncMock(return_value=result))
    service.orders.calculate_price_preview = AsyncMock(return_value=preview)
    service.orders.create_pool_response = AsyncMock(return_value=match)
    service.orders.invite_direct_performer = AsyncMock(return_value=match)
    service.orders.list_order_matches = AsyncMock(return_value=(match,))
    service.orders.accept_direct_match = AsyncMock(return_value=action)
    service.orders.reject_direct_match = AsyncMock(return_value=match)
    service.orders.select_pool_response = AsyncMock(return_value=action)
    service.orders.reject_pool_response = AsyncMock(return_value=match)
    service.orders.submit_order_report = AsyncMock(return_value=report)

    customer_id = uuid4()
    performer_id = uuid4()
    service_id = order.service_id
    request = OrderRequest(
        customer_id=customer_id,
        service_id=service_id,
        start_at=order.start_at,
        end_at=order.end_at,
        care_object_ids=[uuid4()],
    )
    direct_request = DirectOrderRequest(
        **request.model_dump(),
        performer_id=performer_id,
    )
    await order_routes.create_pool(request, service)
    await order_routes.create_direct(direct_request, service)
    await order_routes.price_preview(
        PricePreviewRequest(
            customer_id=customer_id,
            service_id=service_id,
            start_at=order.start_at,
            end_at=order.end_at,
            objects_count=1,
        ),
        service,
    )
    await order_routes.create_pool_response(
        order.id,
        PerformerMatchActionRequest(performer_id=performer_id),
        service,
    )
    await order_routes.invite_direct_performer(
        order.id,
        CustomerDirectPerformerRequest(
            customer_id=customer_id,
            performer_id=performer_id,
        ),
        service,
    )
    await order_routes.publish_pool_order(
        order.id,
        CustomerMatchActionRequest(customer_id=customer_id),
        service,
    )
    await order_routes.list_order_matches(order.id, customer_id, service)
    await order_routes.accept_direct_match(
        match.id,
        PerformerMatchActionRequest(performer_id=performer_id),
        service,
    )
    await order_routes.reject_direct_match(
        match.id,
        PerformerMatchActionRequest(performer_id=performer_id),
        service,
    )
    await order_routes.select_pool_response(
        match.id,
        CustomerMatchActionRequest(customer_id=customer_id),
        service,
    )
    await order_routes.reject_pool_response(
        match.id,
        CustomerMatchActionRequest(customer_id=customer_id),
        service,
    )
    await order_routes.start_order(
        order.id,
        PerformerOrderActionRequest(performer_id=performer_id),
        service,
    )
    await order_routes.finish_order(
        order.id,
        PerformerOrderActionRequest(performer_id=performer_id),
        service,
    )
    await order_routes.submit_order_report(
        order.id,
        OrderReportRequest(performer_id=performer_id, completed_work="Done"),
        service,
    )
    await order_routes.cancel_order(
        order.id,
        CancelOrderRequest(actor_type="customer", actor_id=customer_id),
        service,
    )

    service.orders.create_pool_order.assert_called_once()
    service.orders.submit_order_report.assert_called_once()


@pytest.mark.unit
async def test_support_route_pagination_and_record_mapping() -> None:
    now = datetime.now(UTC)
    record = SimpleNamespace(
        id=uuid4(),
        customer_id=None,
        performer_id=None,
        order_id=None,
        direction="customer",
        type="technical",
        category=None,
        text="Help",
        status="open",
        blockers=[],
        admin_comment=None,
        created_at=now,
        updated_at=now,
        resolved_at=None,
    )
    container: Any = SimpleNamespace(support=SimpleNamespace())
    container.support.list_support_records = AsyncMock(return_value=([record], 1))
    container.support.list_admin_support_records = AsyncMock(return_value=([record], 1))
    user_page = await _user_list(container, "customer", 1, "support", None, 1, 10)
    admin_page = await _admin_list(container, "support", None, 1, 10)
    assert user_page.total == admin_page.total == 1


@pytest.mark.unit
async def test_customer_routes_forward_registration_objects_and_addresses() -> None:
    container: Any = SimpleNamespace(customers=SimpleNamespace())
    now = datetime.now(UTC)
    customer_id = uuid4()
    address_id = uuid4()
    object_id = uuid4()
    customer = SimpleNamespace(
        id=customer_id,
        telegram_id=1,
        full_name="Customer",
        phone="+79990000000",
        telegram_username=None,
        contact_method="telegram",
        city_id=uuid4(),
        status="active",
    )
    care_object = SimpleNamespace(
        id=object_id,
        customer_id=customer_id,
        object_type="pet",
        display_name="Pet",
        age_group="adult",
        species=None,
        breed=None,
        pet_size=None,
        mobility_assistance_required=None,
        routine_notes=None,
        behavior_notes=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    address = SimpleNamespace(
        id=address_id,
        owner_type="customer",
        customer_id=customer_id,
        performer_id=None,
        city_id=customer.city_id,
        district_id=None,
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
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    for name, result in (
        ("get_customer_profile", customer),
        ("register_customer", customer),
        ("update_customer_username", customer),
        ("list_customer_care_objects", (care_object,)),
        ("create_customer_care_object", care_object),
        ("update_customer_care_object", care_object),
        ("list_customer_addresses", (address,)),
        ("create_customer_address", address),
    ):
        setattr(container.customers, name, AsyncMock(return_value=result))
    container.customers.delete_customer_care_object = AsyncMock()
    container.customers.delete_customer_address = AsyncMock()
    city_id = customer.city_id
    legal_id = uuid4()
    await customer_routes.get_profile(1, container)
    await customer_routes.register(
        RegisterCustomerRequest(
            telegram_id=1,
            full_name="Customer",
            phone="+79990000000",
            city_id=city_id,
            contact_method="telegram",
            accepted_legal_document_ids=[legal_id],
        ),
        container,
    )
    await customer_routes.update_telegram_username(
        1, UpdateTelegramUsernameRequest(), container
    )
    await customer_routes.list_care_objects(1, container, "pet")
    await customer_routes.create_care_object(
        1,
        CreateCareObjectRequest(
            object_type="pet", display_name="Pet", age_group="adult"
        ),
        container,
    )
    await customer_routes.update_care_object(
        1,
        object_id,
        CareObjectRequest(display_name="Pet", age_group="adult"),
        container,
    )
    await customer_routes.delete_care_object(1, object_id, container)
    await customer_routes.list_addresses(1, container)
    await customer_routes.create_address(
        1,
        CreateAddressRequest(city_id=city_id, unrestricted_value="Main street, 1"),
        container,
    )
    await customer_routes.delete_address(1, address_id, container)
    container.customers.delete_customer_care_object.assert_awaited_once()


@pytest.mark.unit
async def test_performer_routes_forward_profile_services_and_addresses() -> None:
    container: Any = SimpleNamespace(performers=SimpleNamespace())
    now = datetime.now(UTC)
    performer_id = uuid4()
    service_id = uuid4()
    address_id = uuid4()
    performer = SimpleNamespace(
        id=performer_id,
        telegram_id=2,
        full_name="Performer",
        phone="+79990000000",
        telegram_username=None,
        contact_method="telegram",
        city_id=uuid4(),
        about_text="About",
        status="active",
        is_accepting_orders=True,
        current_address_id=address_id,
    )
    service = SimpleNamespace(
        id=uuid4(),
        performer_id=performer_id,
        service_id=service_id,
        service_code="care",
        service_name="Care",
        service_location_policy="customer_address",
        is_approved=True,
        is_enabled=True,
        admin_max_objects=2,
        performer_max_objects=1,
        constraints={},
        approved_by_admin_id=None,
        approved_at=None,
    )
    address = SimpleNamespace(
        id=address_id,
        owner_type="performer",
        customer_id=None,
        performer_id=performer_id,
        city_id=performer.city_id,
        district_id=None,
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
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    state = SimpleNamespace(state="registered", invitation=None, performer=performer)
    invitation = SimpleNamespace(
        id=uuid4(),
        telegram_id=2,
        status="pending",
        expires_at=None,
        accepted_performer_id=None,
    )
    for name, result in (
        ("get_registration_state", state),
        ("register_performer", performer),
        ("update_performer_username", performer),
        ("list_performer_services_by_telegram", (service,)),
        ("set_performer_service_enabled", service),
        ("set_performer_service_max_objects", service),
        ("set_performer_accepting_orders", performer),
        ("list_performer_addresses", (address,)),
        ("create_performer_address", address),
        ("set_performer_current_address", address),
        ("create_invitation", invitation),
    ):
        setattr(container.performers, name, AsyncMock(return_value=result))
    container.performers.delete_performer_address = AsyncMock()

    await performer_routes.registration_state(2, container)
    await performer_routes.register_by_invitation(
        RegisterPerformerRequest(
            telegram_id=2,
            full_name="Performer",
            phone="+79990000000",
            city_id=performer.city_id,
            contact_method="telegram",
            about_text="About",
            accepted_legal_document_ids=[],
        ),
        container,
    )
    await performer_routes.update_telegram_username(
        2,
        PerformerUsernameRequest(telegram_username="performer"),
        container,
    )
    await performer_routes.list_services_by_telegram(2, container)
    await performer_routes.set_service_enabled(
        2,
        service_id,
        SetPerformerServiceEnabledRequest(is_enabled=True),
        container,
    )
    await performer_routes.set_service_max_objects(
        2,
        service_id,
        SetPerformerServiceMaxObjectsRequest(performer_max_objects=1),
        container,
    )
    await performer_routes.set_accepting_orders(
        2,
        SetAcceptingOrdersRequest(is_accepting_orders=True),
        container,
    )
    await performer_routes.list_addresses(2, container)
    await performer_routes.set_current_address(2, address_id, container)
    await performer_routes.delete_address(2, address_id, container)

    container.performers.delete_performer_address.assert_awaited_once()


@pytest.mark.unit
async def test_admin_routes_cover_session_csrf_notifications_and_operations() -> None:
    admin_id = uuid4()
    now = datetime.now(UTC)
    admin = SimpleNamespace(
        id=admin_id,
        email="admin@test.local",
        full_name="Admin",
        status="active",
        last_login_at=None,
    )
    csrf = str(uuid4())
    session_result = SimpleNamespace(
        admin=admin,
        session_id="session",
        csrf_token=csrf,
    )
    container: Any = SimpleNamespace(
        settings=SimpleNamespace(
            admin_session_ttl_seconds=600,
            environment="test",
        ),
        admin=SimpleNamespace(),
        payments=SimpleNamespace(),
    )
    container.admin.login_admin = AsyncMock(return_value=session_result)
    container.admin.get_current_admin = AsyncMock(return_value=(admin, csrf))
    container.admin.list_admin_notifications = AsyncMock(
        return_value=(
            [
                SimpleNamespace(
                    id=uuid4(),
                    type="order_started",
                    entity_type="order",
                    entity_id=uuid4(),
                    payload={},
                    status="sent",
                    read_at=None,
                    created_at=now,
                    sent_at=now,
                    last_error=None,
                ),
            ],
            1,
        ),
    )
    container.admin.mark_admin_notifications_read = AsyncMock(return_value=1)
    container.admin.logout_admin = AsyncMock()
    container.admin.update_business_setting = AsyncMock(
        return_value=SimpleNamespace(key="fee", value=10, value_type="integer"),
    )
    refund = SimpleNamespace(
        id=uuid4(),
        order_id=uuid4(),
        payment_id=uuid4(),
        refund_type="full",
        amount=Decimal("10"),
        status="pending",
        reason="test",
        provider_refund_id=None,
    )
    container.payments.create_manual_refund = AsyncMock(return_value=refund)
    container.payments.retry_payment_operation = AsyncMock(return_value=None)
    response = Response()
    login_result = await admin_routes.login(
        LoginRequest(email="admin@test.local", password=str(uuid4())),
        response,
        container,
    )
    assert login_result.csrf_token == csrf
    current = await admin_routes.get_current_admin(container, "session")
    assert current[0].id == str(admin_id)
    assert await admin_routes.me(current) == current[0]
    assert await admin_routes.require_admin_csrf(current, csrf) == current
    page = await admin_routes.list_notifications(container, current)
    assert page.total == 1
    marked = await admin_routes.mark_notifications_read(
        MarkAdminNotificationsReadRequest(ids=[uuid4()]),
        container,
        current,
    )
    assert marked.marked == 1
    setting = await admin_routes.update_business_setting(
        "fee",
        UpdateBusinessSettingRequest(value=10),
        container,
        current,
    )
    assert setting.key == "fee"
    refund_response = await admin_routes.create_manual_refund(
        ManualRefundRequest(
            payment_id=refund.payment_id,
            amount=None,
            reason="test",
        ),
        container,
        current,
    )
    assert refund_response.id == str(refund.id)
    await admin_routes.retry_payment_operation(refund.payment_id, container, current)
    await admin_routes.logout(response, container, current)
    container.admin.logout_admin.assert_awaited_once_with("session")


@pytest.mark.unit
async def test_catalog_and_availability_routes_map_service_results() -> None:
    city = SimpleNamespace(
        id=uuid4(),
        name="Moscow",
        slug="moscow",
        timezone="Europe/Moscow",
        is_active=True,
    )
    container: Any = SimpleNamespace(
        catalog=SimpleNamespace(), availability=SimpleNamespace()
    )
    container.catalog.list_cities = AsyncMock(return_value=(city,))
    container.catalog.get_catalog = AsyncMock(
        return_value=SimpleNamespace(categories=())
    )
    container.catalog.get_support_contact = AsyncMock(
        return_value=SimpleNamespace(label="Support", telegram_url=None),
    )
    container.catalog.list_legal_documents = AsyncMock(return_value=())
    assert (await catalog_routes.list_cities(container))[0].slug == "moscow"
    assert (await catalog_routes.get_catalog(container)).categories == []
    assert (await catalog_routes.get_support_contact(container)).label == "Support"
    assert await catalog_routes.list_legal_documents(container) == []

    performer_id = uuid4()
    schedule = PerformerScheduleDTO(
        id=uuid4(),
        performer_id=performer_id,
        schedule_type="every_day",
        work_days=None,
        work_start_time=datetime.strptime("09:00", "%H:%M").time(),
        work_end_time=datetime.strptime("18:00", "%H:%M").time(),
        is_active=True,
    )
    override = CalendarOverrideDTO(
        id=uuid4(),
        performer_id=performer_id,
        override_type="unavailable",
        starts_at=datetime(2026, 1, 2, tzinfo=UTC),
        ends_at=datetime(2026, 1, 3, tzinfo=UTC),
        comment="holiday",
        timezone="UTC",
        is_active=True,
    )
    suitable = SuitablePerformerDTO(
        performer_id=performer_id,
        full_name="Performer",
        service_id=uuid4(),
        service_code="care",
        service_name="Care",
        performer_max_objects=1,
        distance_km=Decimal("1.2"),
        current_address_id=None,
    )
    container.availability.set_performer_schedule = AsyncMock(return_value=schedule)
    container.availability.add_calendar_override = AsyncMock(return_value=override)
    container.availability.get_performer_calendar = AsyncMock(
        return_value=(schedule, (override,), ()),
    )
    container.availability.check_performer_availability = AsyncMock(
        return_value=AvailabilityCheckDTO(performer_id, True, ()),
    )
    container.availability.find_suitable_performers = AsyncMock(
        return_value=(suitable,)
    )
    await availability_routes.set_schedule(
        1,
        SetScheduleRequest(
            schedule_type="every_day",
            work_start_time="09:00",
            work_end_time="18:00",
        ),
        container,
    )
    await availability_routes.add_override(
        1,
        AddOverrideRequest(
            override_type="unavailable",
            starts_at=override.starts_at,
            ends_at=override.ends_at,
        ),
        container,
    )
    await availability_routes.get_calendar(1, container)
    await availability_routes.check_availability(
        performer_id,
        uuid4(),
        override.starts_at,
        override.ends_at,
        container,
    )
    result = await availability_routes.find_suitable_performers(
        city_id=uuid4(),
        service_id=suitable.service_id,
        starts_at=override.starts_at,
        ends_at=override.ends_at,
        objects_count=1,
        container=container,
    )
    assert result[0].performer_id == str(performer_id)


@pytest.mark.unit
async def test_payment_webhook_route_validates_signature_and_dispatches_command() -> (
    None
):
    order_id = uuid4()
    payload: dict[str, object] = {
        "TerminalKey": "terminal",
        "OrderId": str(order_id),
        "Success": True,
        "Status": "CONFIRMED",
        "PaymentId": "provider-payment",
        "Amount": 1234,
        "Date": "2026-01-01T10:00:00Z",
    }
    password = str(uuid4())
    payload["Token"] = _sign_payload(payload, password)

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": json.dumps(payload).encode()}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/payments/webhooks/tbank",
            "headers": [],
            "query_string": b"",
        },
        receive,
    )
    container: Any = SimpleNamespace(
        settings=SimpleNamespace(
            tbank_terminal_key="terminal",
            tbank_password=password,
        ),
        payments=SimpleNamespace(apply_payment_webhook=AsyncMock()),
    )
    response = await tbank_webhook(request, container)
    assert response.status_code == 200
    container.payments.apply_payment_webhook.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.parametrize("amount", ["not-an-integer", 0, True, " 100", "+100"])
async def test_payment_webhook_route_rejects_invalid_amount(amount: object) -> None:
    from fastapi import HTTPException

    password = str(uuid4())
    payload: dict[str, object] = {
        "TerminalKey": "terminal",
        "OrderId": str(uuid4()),
        "Success": True,
        "Status": "CONFIRMED",
        "PaymentId": "provider-payment",
        "Amount": amount,
    }
    payload["Token"] = _sign_payload(payload, password)

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": json.dumps(payload).encode()}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/payments/webhooks/tbank",
            "headers": [],
            "query_string": b"",
        },
        receive,
    )
    container: Any = SimpleNamespace(
        settings=SimpleNamespace(
            tbank_terminal_key="terminal",
            tbank_password=password,
        ),
        payments=SimpleNamespace(apply_payment_webhook=AsyncMock()),
    )

    with pytest.raises(HTTPException) as error:
        await tbank_webhook(request, container)

    assert error.value.status_code == 400
    container.payments.apply_payment_webhook.assert_not_awaited()


@pytest.mark.unit
async def test_payment_webhook_route_rejects_invalid_terminal() -> None:
    from fastapi import HTTPException

    payload = {
        "TerminalKey": "wrong",
        "OrderId": str(uuid4()),
        "Success": True,
        "Status": "CONFIRMED",
        "PaymentId": "provider-payment",
        "Amount": 1234,
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": json.dumps(payload).encode()}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/payments/webhooks/tbank",
            "headers": [],
            "query_string": b"",
        },
        receive,
    )
    container: Any = SimpleNamespace(
        settings=SimpleNamespace(
            tbank_terminal_key="terminal",
            tbank_password=str(uuid4()),
        ),
        payments=SimpleNamespace(apply_payment_webhook=AsyncMock()),
    )
    with pytest.raises(HTTPException, match="terminal"):
        await tbank_webhook(request, container)


@pytest.mark.unit
async def test_payment_webhook_route_rejects_missing_payment_and_invalid_order() -> (
    None
):
    from fastapi import HTTPException

    password = str(uuid4())
    payload: dict[str, object] = {
        "TerminalKey": "terminal",
        "OrderId": "not-a-uuid",
        "Success": True,
        "Status": "CONFIRMED",
    }
    payload["Token"] = _sign_payload(payload, password)

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": json.dumps(payload).encode()}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/payments/webhooks/tbank",
            "headers": [],
            "query_string": b"",
        },
        receive,
    )
    container: Any = SimpleNamespace(
        settings=SimpleNamespace(
            tbank_terminal_key="terminal",
            tbank_password=password,
        ),
        payments=SimpleNamespace(apply_payment_webhook=AsyncMock()),
    )
    with pytest.raises(HTTPException, match="payment webhook"):
        await tbank_webhook(request, container)


@pytest.mark.unit
def test_payment_webhook_helpers_parse_date_and_remove_sensitive_payload_fields() -> (
    None
):
    raw = {
        "TerminalKey": "terminal",
        "OrderId": str(uuid4()),
        "Success": True,
        "Status": "CONFIRMED",
        "PaymentId": "payment",
        "Amount": 100,
        "Token": "secret",
        "Password": "secret",
    }
    assert _paid_at({"Date": "2026-01-01T10:00:00Z"}).tzinfo == UTC
    assert _paid_at({"Date": "invalid"}).tzinfo == UTC
    safe = _safe_payload(raw)
    assert "Token" not in safe
    assert "Password" not in safe

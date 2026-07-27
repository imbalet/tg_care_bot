from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.domain import ConflictError
from backend.modules.admin.infrastructure import AdminModel
from backend.modules.catalog.infrastructure import (
    CityModel,
    ServiceCategoryModel,
    ServiceModel,
)
from backend.modules.customers.infrastructure import CustomerModel
from backend.modules.orders.infrastructure.persistence.models import (
    OrderModel,
    OrderStatusHistoryModel,
)
from backend.modules.orders.infrastructure.persistence.order_queries import (
    SqlAlchemyMyOrdersQueryService,
)
from backend.modules.orders.infrastructure.persistence.order_repositories import (
    SqlAlchemyOrderRepository,
)
from backend.modules.payments.infrastructure import PaymentModel
from backend.modules.performers.infrastructure import PerformerModel


@pytest.mark.integration
async def test_order_repository_enforces_execution_lifecycle(
    session: AsyncSession,
) -> None:
    city = await session.scalar(select(CityModel).where(CityModel.is_active.is_(True)))
    service = await session.scalar(
        select(ServiceModel).where(ServiceModel.is_active.is_(True)),
    )
    assert city is not None
    assert service is not None

    customer = CustomerModel(
        telegram_id=uuid4().int % 10**12,
        full_name="Lifecycle customer",
        phone="+79990000001",
        contact_method="telegram",
        city_id=city.id,
    )
    performer = PerformerModel(
        telegram_id=uuid4().int % 10**12,
        full_name="Lifecycle performer",
        phone="+79990000002",
        contact_method="telegram",
        city_id=city.id,
        status="active",
        is_accepting_orders=True,
    )
    session.add_all((customer, performer))
    await session.flush()

    start_at = datetime.now(UTC) + timedelta(hours=2)
    order = OrderModel(
        customer_id=customer.id,
        service_id=service.id,
        service_code=service.code,
        service_name=service.name,
        schedule_policy=service.schedule_policy,
        photo_policy="forbidden",
        matching_mode="direct",
        status="confirmed",
        selected_performer_id=performer.id,
        location_source="customer_address",
        start_at=start_at,
        end_at=start_at + timedelta(hours=1),
        objects_count=1,
        base_price=Decimal("600.00"),
        price_type="hourly",
        object_multiplier=Decimal("1"),
        service_amount=Decimal("600.00"),
        platform_fee_percent_at_order=Decimal("10"),
        platform_fee_amount=Decimal("60.00"),
        performer_amount=Decimal("540.00"),
        total_amount=Decimal("600.00"),
        matching_deadline_at=start_at - timedelta(minutes=30),
    )
    session.add(order)
    await session.flush()

    repository = SqlAlchemyOrderRepository(session)
    with pytest.raises(ConflictError, match="payment is not confirmed"):
        await repository.start_order(
            order_id=order.id,
            performer_id=performer.id,
            start_button_before_minutes=180,
        )
    with pytest.raises(ConflictError, match="payment is not confirmed"):
        await repository.start_order_by_customer(
            order_id=order.id,
            customer_id=customer.id,
            start_button_before_minutes=180,
        )

    payment = PaymentModel(
        order_id=order.id,
        performer_id=performer.id,
        attempt_number=1,
        provider="test",
        idempotency_key=f"lifecycle-{order.id}",
        amount=Decimal("600.00"),
        status="succeeded",
        provider_status="CONFIRMED",
        expires_at=start_at + timedelta(hours=1),
        paid_at=datetime.now(UTC),
        applied_at=datetime.now(UTC),
    )
    session.add(payment)
    await session.flush()
    order.active_payment_id = payment.id

    started = await repository.start_order(
        order_id=order.id,
        performer_id=performer.id,
        start_button_before_minutes=180,
    )
    assert started.status == "in_progress"

    finished = await repository.finish_order(
        order_id=order.id,
        performer_id=performer.id,
        report_due_at=datetime.now(UTC) + timedelta(hours=2),
    )
    assert finished.status == "waiting_report"

    report = await repository.submit_report(
        order_id=order.id,
        performer_id=performer.id,
        completed_work="Work completed",
        comment=None,
        problem_flag=False,
        problem_description=None,
        confirmation_deadline_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert report.completed_work == "Work completed"

    with pytest.raises(ConflictError):
        await repository.start_order(
            order_id=order.id,
            performer_id=performer.id,
            start_button_before_minutes=180,
        )

    history = (
        await session.scalars(
            select(OrderStatusHistoryModel)
            .where(OrderStatusHistoryModel.order_id == order.id)
            .order_by(OrderStatusHistoryModel.created_at),
        )
    ).all()
    assert [(item.from_status, item.to_status) for item in history] == [
        ("confirmed", "in_progress"),
        ("in_progress", "waiting_report"),
        ("waiting_report", "report_submitted"),
    ]


@pytest.mark.integration
async def test_customer_order_archive_treats_empty_category_as_all_directions(
    session: AsyncSession,
) -> None:
    assert AdminModel.__tablename__ == "admins"
    city = await session.scalar(select(CityModel).where(CityModel.is_active.is_(True)))
    service = await session.scalar(
        select(ServiceModel).where(ServiceModel.is_active.is_(True)),
    )
    assert city is not None
    assert service is not None
    category = await session.scalar(
        select(ServiceCategoryModel).where(
            ServiceCategoryModel.id == service.category_id,
        ),
    )
    assert category is not None

    customer = CustomerModel(
        telegram_id=uuid4().int % 10**12,
        full_name="Order list customer",
        phone="+79990000003",
        contact_method="telegram",
        city_id=city.id,
    )
    session.add(customer)
    await session.flush()

    start_at = datetime.now(UTC) + timedelta(days=1)
    session.add(
        OrderModel(
            customer_id=customer.id,
            service_id=service.id,
            service_code=service.code,
            service_name=service.name,
            schedule_policy=service.schedule_policy,
            photo_policy=service.photo_policy,
            matching_mode="pool",
            status="cancelled",
            location_source="performer_address",
            start_at=start_at,
            end_at=start_at + timedelta(hours=1),
            objects_count=1,
            base_price=Decimal("600.00"),
            price_type=service.price_type,
            object_multiplier=Decimal("1"),
            service_amount=Decimal("600.00"),
            platform_fee_percent_at_order=Decimal("10"),
            platform_fee_amount=Decimal("60.00"),
            performer_amount=Decimal("540.00"),
            total_amount=Decimal("600.00"),
            matching_deadline_at=start_at - timedelta(minutes=30),
        ),
    )
    await session.flush()

    query_service = SqlAlchemyMyOrdersQueryService(session)
    archive = await query_service.list_customer_orders(
        customer_id=customer.id,
        group="archive",
        page=1,
        page_size=5,
        category_code="",
    )
    active = await query_service.list_customer_orders(
        customer_id=customer.id,
        group="active",
        page=1,
        page_size=5,
        category_code="",
    )

    assert archive.total_items == 1
    assert archive.items[0].status == "cancelled"
    assert active.total_items == 0

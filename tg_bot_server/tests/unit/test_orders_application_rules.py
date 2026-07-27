from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.common.domain import ValidationError
from backend.modules.files.application import FileDTO
from backend.modules.orders.application.dto import (
    OrderCareObjectSnapshot,
    OrderReportDTO,
    ServicePricingDTO,
)
from backend.modules.orders.application.use_cases import (
    CancelOrderCommand,
    CancelOrderUseCase,
    CreateDirectOrderCommand,
    CreateDirectOrderUseCase,
    CreatePoolOrderCommand,
    CreatePoolOrderUseCase,
    FinishOrderCommand,
    FinishOrderUseCase,
    StartOrderCommand,
    StartOrderUseCase,
    SubmitOrderReportCommand,
    SubmitOrderReportUseCase,
)
from tests.support.fakes import FakeObjectStorage


def _service(
    *,
    location_policy: str = "customer_address",
    photo_policy: str = "not_allowed",
    object_type: str = "pet",
) -> ServicePricingDTO:
    return ServicePricingDTO(
        service_id=uuid4(),
        category_id=uuid4(),
        category_object_type=object_type,
        max_objects_per_order=3,
        service_code="care",
        service_name="Care service",
        price_type="hourly",
        base_price=Decimal("600.00"),
        location_policy=location_policy,
        schedule_policy="working_hours",
        photo_policy=photo_policy,
        duration_step_minutes=30,
        min_duration_minutes=30,
        max_duration_minutes=240,
        is_active=True,
    )


def _snapshot(*, object_type: str = "pet") -> OrderCareObjectSnapshot:
    return OrderCareObjectSnapshot(
        care_object_id=uuid4(),
        object_type=object_type,
        display_name_at_order="Buddy",
        summary_at_order="small pet",
    )


def _command(service: ServicePricingDTO) -> CreatePoolOrderCommand:
    start = datetime.now(UTC) + timedelta(days=1)
    return CreatePoolOrderCommand(
        customer_id=uuid4(),
        service_id=service.service_id,
        start_at=start,
        end_at=start + timedelta(hours=1),
        care_object_ids=(uuid4(),),
        address_id=uuid4(),
        customer_comment=None,
        report_photo_consent=None,
        option_values={},
        location_source=None,
    )


def _order_repository(
    service: ServicePricingDTO,
    snapshot: OrderCareObjectSnapshot,
) -> AsyncMock:
    repository = AsyncMock()
    repository.get_customer_timezone.return_value = "UTC"
    repository.list_care_object_snapshots.return_value = (snapshot,)
    repository.customer_address_is_active.return_value = True
    repository.service_options_exist.return_value = True
    repository.get_service_pricing.return_value = service
    repository.get_object_multiplier.return_value = Decimal("1")
    repository.get_decimal_setting.return_value = Decimal("10")
    repository.get_integer_setting.side_effect = lambda key: {
        "minimum_order_lead_minutes": 30,
        "payment_provider_hold_limit_minutes": 48 * 60,
        "report_confirmation_window_minutes": 60,
        "matching_close_before_start_minutes": 30,
        "direct_response_window_minutes": 180,
        "report_deadline_minutes": 30,
        "customer_cancel_before_start_minutes": 360,
        "performer_cancel_before_start_minutes": 180,
    }.get(key)
    return repository


@pytest.mark.unit
async def test_create_pool_order_validates_and_persists_price_snapshot() -> None:
    service = _service()
    snapshot = _snapshot()
    repository = _order_repository(service, snapshot)
    expected = SimpleNamespace(id=uuid4())
    repository.create_pool.return_value = expected

    result = await CreatePoolOrderUseCase(repository, repository).execute(
        _command(service),
    )

    assert result.id == expected.id
    repository.create_pool.assert_awaited_once()
    call = repository.create_pool.await_args.kwargs
    assert call["object_snapshots"] == (snapshot,)
    assert call["price"].total_amount == Decimal("600.00")


@pytest.mark.unit
async def test_create_order_rejects_category_mismatch() -> None:
    service = _service(object_type="child")
    repository = _order_repository(service, _snapshot(object_type="pet"))

    with pytest.raises(ValidationError, match="category"):
        await CreatePoolOrderUseCase(repository, repository).execute(_command(service))


@pytest.mark.unit
async def test_create_boarding_order_rejects_customer_address() -> None:
    service = _service(location_policy="performer_address")
    repository = _order_repository(service, _snapshot())

    with pytest.raises(ValidationError, match="must not use customer address"):
        await CreatePoolOrderUseCase(repository, repository).execute(
            _command(service),
        )


@pytest.mark.unit
async def test_create_selectable_location_order_accepts_performer_address() -> None:
    service = _service(location_policy="customer_or_performer_address")
    repository = _order_repository(service, _snapshot())
    expected = SimpleNamespace(id=uuid4())
    repository.create_pool.return_value = expected
    command = replace(
        _command(service),
        address_id=None,
        location_source="performer_address",
    )

    result = await CreatePoolOrderUseCase(repository, repository).execute(command)

    assert result.id == expected.id
    assert repository.create_pool.await_args.kwargs["data"].location_source == (
        "performer_address"
    )


@pytest.mark.unit
async def test_create_selectable_location_order_accepts_customer_address() -> None:
    service = _service(location_policy="customer_or_performer_address")
    repository = _order_repository(service, _snapshot())
    expected = SimpleNamespace(id=uuid4())
    repository.create_pool.return_value = expected
    command = replace(_command(service), location_source="customer_address")

    await CreatePoolOrderUseCase(repository, repository).execute(command)

    assert repository.customer_address_is_active.await_count == 1
    assert repository.create_pool.await_args.kwargs["data"].location_source == (
        "customer_address"
    )


@pytest.mark.unit
async def test_create_selectable_location_order_requires_location_source() -> None:
    service = _service(location_policy="customer_or_performer_address")
    repository = _order_repository(service, _snapshot())

    with pytest.raises(ValidationError, match="location source"):
        await CreatePoolOrderUseCase(repository, repository).execute(
            replace(_command(service), address_id=None, location_source=None),
        )


@pytest.mark.unit
async def test_selectable_location_rejects_customer_address_for_performer():
    service = _service(location_policy="customer_or_performer_address")
    repository = _order_repository(service, _snapshot())

    with pytest.raises(ValidationError, match="must not use customer address"):
        await CreatePoolOrderUseCase(repository, repository).execute(
            replace(_command(service), location_source="performer_address"),
        )


@pytest.mark.unit
async def test_create_fixed_location_order_rejects_conflicting_source() -> None:
    service = _service(location_policy="customer_address")
    repository = _order_repository(service, _snapshot())

    with pytest.raises(ValidationError, match="not allowed"):
        await CreatePoolOrderUseCase(repository, repository).execute(
            replace(_command(service), location_source="performer_address"),
        )


@pytest.mark.unit
async def test_create_direct_selectable_location_order_uses_selected_source() -> None:
    service = _service(location_policy="customer_or_performer_address")
    repository = _order_repository(service, _snapshot())
    repository.get_customer_city_id.return_value = uuid4()
    performer_id = uuid4()
    availability = AsyncMock()
    availability.find_suitable_performers.return_value = [
        SimpleNamespace(performer_id=performer_id),
    ]
    repository.create_direct.return_value = SimpleNamespace(id=uuid4())
    command = _command(service)
    direct = CreateDirectOrderCommand(
        **replace(
            command,
            address_id=None,
            location_source="performer_address",
        ).__dict__,
        performer_id=performer_id,
    )

    await CreateDirectOrderUseCase(repository, repository, availability).execute(direct)

    assert repository.create_direct.await_args.kwargs["data"].location_source == (
        "performer_address"
    )


@pytest.mark.unit
async def test_create_photo_consent_is_required_only_for_restricted_services() -> None:
    service = _service(photo_policy="requires_customer_consent")
    repository = _order_repository(service, _snapshot())

    with pytest.raises(ValidationError, match="consent"):
        await CreatePoolOrderUseCase(repository, repository).execute(
            replace(_command(service), report_photo_consent=None),
        )


@pytest.mark.unit
async def test_create_order_rejects_missing_objects() -> None:
    service = _service()
    repository = _order_repository(service, _snapshot())

    with pytest.raises(ValidationError, match="care objects"):
        await CreatePoolOrderUseCase(repository, repository).execute(
            replace(_command(service), care_object_ids=()),
        )


@pytest.mark.unit
async def test_create_order_rejects_inactive_customer_address() -> None:
    service = _service()
    repository = _order_repository(service, _snapshot())
    repository.customer_address_is_active.return_value = False

    with pytest.raises(ValidationError, match="address"):
        await CreatePoolOrderUseCase(repository, repository).execute(
            _command(service),
        )


@pytest.mark.unit
async def test_create_order_rejects_unknown_service_option() -> None:
    service = _service()
    repository = _order_repository(service, _snapshot())
    repository.service_options_exist.return_value = False

    with pytest.raises(ValidationError, match="option"):
        await CreatePoolOrderUseCase(repository, repository).execute(
            _command(service),
        )


@pytest.mark.unit
async def test_create_order_rejects_consent_for_service_without_photo_policy() -> None:
    service = _service(photo_policy="not_allowed")
    repository = _order_repository(service, _snapshot())

    with pytest.raises(ValidationError, match="consent"):
        await CreatePoolOrderUseCase(repository, repository).execute(
            replace(_command(service), report_photo_consent=True),
        )


@pytest.mark.unit
async def test_direct_order_rejects_unsuitable_performer() -> None:
    service = _service()
    repository = _order_repository(service, _snapshot())
    repository.get_customer_city_id.return_value = uuid4()
    availability = AsyncMock()
    availability.find_suitable_performers.return_value = [
        SimpleNamespace(performer_id=uuid4()),
    ]
    command = _command(service)
    direct = CreateDirectOrderCommand(**command.__dict__, performer_id=uuid4())

    with pytest.raises(ValidationError, match="not suitable"):
        await CreateDirectOrderUseCase(repository, repository, availability).execute(
            direct,
        )


@pytest.mark.unit
async def test_start_finish_and_cancel_delegate_policy_to_repository() -> None:
    repository = AsyncMock()
    pricing = AsyncMock()
    pricing.get_integer_setting.side_effect = lambda key: {
        "report_deadline_minutes": 30,
        "customer_cancel_before_start_minutes": 360,
        "performer_cancel_before_start_minutes": 180,
    }.get(key)
    order_id = uuid4()
    performer_id = uuid4()

    await StartOrderUseCase(repository).execute(
        StartOrderCommand(order_id, performer_id),
    )
    await FinishOrderUseCase(repository, pricing).execute(
        FinishOrderCommand(order_id, performer_id),
    )
    await CancelOrderUseCase(repository, pricing).execute(
        CancelOrderCommand(order_id, "customer", uuid4(), reason="changed_plans"),
    )

    repository.start_order.assert_awaited_once_with(
        order_id=order_id,
        performer_id=performer_id,
    )
    repository.finish_order.assert_awaited_once()
    repository.cancel_order.assert_awaited_once_with(
        order_id=order_id,
        actor_type="customer",
        actor_id=repository.cancel_order.await_args.kwargs["actor_id"],
        customer_deadline_minutes=360,
        performer_deadline_minutes=180,
        reason="changed_plans",
        comment=None,
    )


@pytest.mark.unit
async def test_report_accepts_valid_image_and_links_it_to_report() -> None:
    file_id = uuid4()
    report_id = uuid4()
    order_id = uuid4()
    file_repository = AsyncMock()
    file_repository.get.return_value = FileDTO(
        id=file_id,
        telegram_file_id=None,
        bucket="test",
        storage_key="reports/photo.png",
        original_name="photo.png",
        mime_type="image/png",
        size_bytes=68,
        checksum="checksum",
        status="uploaded",
        created_at=datetime.now(UTC),
        deleted_at=None,
    )
    order_repository = AsyncMock()
    order_repository.get_order.return_value = SimpleNamespace(
        photo_policy="required",
    )
    order_repository.submit_report.return_value = OrderReportDTO(
        id=report_id,
        order_id=order_id,
        performer_id=uuid4(),
        completed_work="Walk completed",
        comment=None,
        problem_flag=False,
        problem_description=None,
        submitted_at=datetime.now(UTC),
        file_ids=(),
    )
    storage = FakeObjectStorage()
    storage.objects["reports/photo.png"] = (
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 60,
        "image/png",
    )

    result = await SubmitOrderReportUseCase(
        order_repository,
        file_repository,
        storage,
    ).execute(
        SubmitOrderReportCommand(
            order_id=order_id,
            performer_id=uuid4(),
            completed_work="Walk completed",
            comment=None,
            problem_flag=False,
            problem_description=None,
            file_ids=(file_id,),
        ),
    )

    assert result.file_ids == (file_id,)
    file_repository.add_link.assert_awaited_once()
    assert file_repository.add_link.await_args.args[0].entity_id == report_id

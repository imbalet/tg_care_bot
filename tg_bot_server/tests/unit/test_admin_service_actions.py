from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from starlette.requests import Request

from backend.modules.admin.presentation.surface import PerformerView
from backend.modules.catalog.application.dto import (
    CatalogDTO,
    ServiceCategoryDTO,
    ServiceDTO,
)
from backend.modules.performers.infrastructure import PerformerModel


def _catalog(*services: ServiceDTO) -> CatalogDTO:
    return CatalogDTO(
        categories=(
            ServiceCategoryDTO(
                id=uuid4(),
                code="care",
                name="Care",
                care_object_type="pet",
                max_objects_per_order=5,
                is_active=True,
                sort_order=0,
                services=services,
            ),
        ),
    )


def _service(*, code: str, name: str) -> ServiceDTO:
    return ServiceDTO(
        id=uuid4(),
        code=code,
        name=name,
        description=name,
        price_type="fixed",
        base_price=Decimal("0"),
        location_policy="performer_address",
        photo_policy="optional",
        schedule_policy="any",
        allows_multiday=False,
        min_duration_minutes=None,
        max_duration_minutes=None,
        duration_step_minutes=None,
        is_active=True,
        sort_order=0,
        options=(),
    )


def _request(body: bytes, *, admin_id):
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/admin/action",
            "query_string": b"",
            "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "root_path": "",
            "http_version": "1.1",
            "state": {"admin_user": SimpleNamespace(id=admin_id)},
        },
        receive,
    )
    return request


async def test_approve_service_action_accepts_multiple_services() -> None:
    first = _service(code="walk", name="Walk")
    second = _service(code="feed", name="Feed")
    performers = SimpleNamespace(approve_performer_service=AsyncMock())
    container = SimpleNamespace(
        catalog=SimpleNamespace(
            get_catalog=AsyncMock(return_value=_catalog(first, second))
        ),
        performers=performers,
    )
    view = PerformerView(PerformerModel, container)
    performer_id = uuid4()
    admin_id = uuid4()
    body = (
        f"service_ids={first.id}&service_ids={second.id}&"
        "admin_max_objects=2&constraints=%7B%7D"
    ).encode()

    result = await view.approve_service_action(
        _request(body, admin_id=admin_id),
        [str(performer_id)],
    )

    assert result == "Approved performer services: 2"
    assert performers.approve_performer_service.await_count == 2
    calls = performers.approve_performer_service.await_args_list
    assert {call.args[0].service_id for call in calls} == {first.id, second.id}


async def test_approve_service_action_form_is_postable_and_has_multi_select() -> None:
    service = _service(code="walk", name="Walk")
    container = SimpleNamespace(
        catalog=SimpleNamespace(get_catalog=AsyncMock(return_value=_catalog(service))),
    )
    view = PerformerView(PerformerModel, container)
    request = _request(b"", admin_id=uuid4())

    actions = await view.get_all_actions(request)
    action = next(item for item in actions if item["name"] == "approve_service")

    assert "<form>" in action["form"]
    assert 'name="service_ids"' in action["form"]
    assert "multiple" in action["form"]
    assert str(service.id) in action["form"]

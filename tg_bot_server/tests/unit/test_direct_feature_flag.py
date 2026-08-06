from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.common.domain import NotFoundError
from backend.modules.orders.application import features
from backend.modules.orders.presentation.api import routes
from backend.modules.orders.presentation.api.schemas import DirectOrderRequest


@pytest.mark.asyncio
async def test_direct_order_route_is_disabled_without_calling_use_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(features, "DIRECT_ORDERS_ENABLED", False)
    orders = SimpleNamespace(create_direct_order=AsyncMock())
    container = SimpleNamespace(orders=orders)
    request = DirectOrderRequest(
        customer_id=uuid4(),
        performer_id=uuid4(),
        service_id=uuid4(),
        start_at="2026-08-10T10:00:00+03:00",
        end_at="2026-08-10T11:00:00+03:00",
        care_object_ids=[uuid4()],
    )

    with pytest.raises(NotFoundError, match="temporarily unavailable"):
        await routes.create_direct(request, container)

    orders.create_direct_order.assert_not_awaited()

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from backend.modules.orders.infrastructure.persistence.models import (
    OrderAddressSnapshotModel,
)
from backend.modules.orders.infrastructure.persistence.order_repositories import (
    SqlAlchemyOrderRepository,
)


@pytest.mark.unit
async def test_customer_address_snapshot_copies_immutable_location_data() -> None:
    session = AsyncMock()
    session.add = Mock()
    address_id = uuid4()
    order_id = uuid4()
    address = SimpleNamespace(
        id=address_id,
        address_text="Ростов-на-Дону, ул. Тестовая, 1",
        fias_id="fias-id",
        latitude=47.2,
        longitude=39.7,
        geocoding_provider="dadata",
        geocoding_quality="high",
        entrance="2",
        floor="3",
        apartment="45",
        comment="Домофон 123",
    )
    session.execute.return_value = SimpleNamespace(
        one_or_none=Mock(
            return_value=(
                address,
                "Ростов-на-Дону",
                "Центральный",
            )
        )
    )

    await SqlAlchemyOrderRepository(session)._save_address_snapshot(
        order_id,
        address_id,
    )

    snapshot = session.add.call_args.args[0]
    assert isinstance(snapshot, OrderAddressSnapshotModel)
    assert snapshot.order_id == order_id
    assert snapshot.source_address_id == address_id
    assert snapshot.city_name == "Ростов-на-Дону"
    assert snapshot.district_name == "Центральный"
    assert snapshot.address_text == address.address_text
    assert snapshot.apartment == "45"
